import json
import re
from datetime import timedelta

from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone

from .models import AttendanceQR

_IDENTIFIER_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')


def _safe_identifier(value: str, label: str) -> str:
    if not value or not _IDENTIFIER_RE.match(value):
        raise ValueError(f'Invalid {label}: {value!r}')
    return connection.ops.quote_name(value)


def _resolve_column(schema_name: str, table_name: str, preferred: str, *, fallbacks=None, required=False):
    candidates = []
    if preferred:
        candidates.append(preferred)
    for item in (fallbacks or []):
        if item and item not in candidates:
            candidates.append(item)

    with connection.cursor() as cursor:
        for candidate in candidates:
            cursor.execute(
                '''
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s AND column_name = %s
                LIMIT 1
                ''',
                [schema_name, table_name, candidate],
            )
            if cursor.fetchone():
                return connection.ops.quote_name(candidate), candidate

    if required:
        raise ValueError(f'Column not found: {preferred!r}')
    return None, None


def _to_text(value):
    if value is None:
        return ''
    return str(value).strip()


def _to_int(value):
    if value is None:
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def login_page(request):
    return render(request, 'login.html')


@csrf_exempt
def student_login(request):
    if request.method != 'POST':
        return JsonResponse({'detail': 'Method not allowed'}, status=405)

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except Exception:
        return JsonResponse({'detail': 'Invalid JSON body'}, status=400)

    email = (payload.get('email') or '').strip()
    if not email:
        return JsonResponse({'detail': 'Please enter your Aptem email'}, status=400)

    schema_name = settings.KBC_TABLE_SCHEMA
    table_name = settings.KBC_TABLE_NAME

    try:
        schema = _safe_identifier(schema_name, 'schema name')
        table = _safe_identifier(table_name, 'table name')

        email_col, _ = _resolve_column(
            schema_name,
            table_name,
            settings.KBC_EMAIL_COLUMN,
            required=True,
        )
        id_col, _ = _resolve_column(
            schema_name,
            table_name,
            getattr(settings, 'KBC_ID_COLUMN', 'ID'),
            fallbacks=['ID', 'id'],
            required=False,
        )
        name_col, _ = _resolve_column(
            schema_name,
            table_name,
            getattr(settings, 'KBC_NAME_COLUMN', 'FullName'),
            fallbacks=['FullName', 'FirstName'],
            required=False,
        )
        group_col, _ = _resolve_column(
            schema_name,
            table_name,
            getattr(settings, 'KBC_GROUP_COLUMN', 'Group'),
            fallbacks=['Group', 'Program Name'],
            required=False,
        )
    except ValueError:
        return JsonResponse({'detail': 'Server configuration error'}, status=500)

    select_fields = ['1 AS ok']
    if id_col:
        select_fields.append(f'{id_col} AS student_id')
    if name_col:
        select_fields.append(f'{name_col} AS student_name')
    if group_col:
        select_fields.append(f'{group_col} AS student_group')

    sql = (
        f"SELECT {', '.join(select_fields)} "
        f"FROM {schema}.{table} "
        f"WHERE LOWER({email_col}) = LOWER(%s) "
        "LIMIT 1"
    )

    with connection.cursor() as cursor:
        cursor.execute(sql, [email])
        row = cursor.fetchone()
        if row is None:
            return JsonResponse({'ok': False, 'detail': 'Please enter your Aptem email'}, status=401)
        columns = [col[0] for col in cursor.description]

    row_data = dict(zip(columns, row))

    response_data = {'ok': True, 'message': 'Login successful.'}
    student_id = _to_int(row_data.get('student_id'))
    student_name = _to_text(row_data.get('student_name'))
    student_group = _to_text(row_data.get('student_group'))
    now = timezone.now()

    existing_record = None
    if student_id is not None:
        existing_record = AttendanceQR.objects.filter(id=student_id).only('date').first()
    else:
        existing_record = AttendanceQR.objects.filter(email__iexact=email).order_by('-date').only('date').first()

    if existing_record and existing_record.date:
        next_allowed_at = existing_record.date + timedelta(hours=24)
        if now < next_allowed_at:
            next_allowed_local = timezone.localtime(next_allowed_at)
            return JsonResponse(
                {
                    'ok': False,
                    'detail': 'Attendance already recorded.',
                    'next_allowed_at': next_allowed_local.isoformat(),
                },
                status=429,
            )

    record_defaults = {
        'kbc_id': student_id,
        'name': student_name,
        'group': student_group,
        'email': email,
        'date': now,
        'time': timezone.localtime().time().replace(microsecond=0),
    }

    if student_id is not None:
        AttendanceQR.objects.update_or_create(
            id=student_id,
            defaults=record_defaults,
        )
    else:
        AttendanceQR.objects.create(**record_defaults)

    if student_id is not None:
        response_data['student_id'] = student_id
    if student_name:
        response_data['name'] = student_name
    if student_group:
        response_data['group'] = student_group

    return JsonResponse(response_data)

