"""Known headers and explicit column choices for prospect imports."""

import re
import unicodedata


COORDINATE_COLUMNS = {
    'email': ('email', 'courriel', 'adresseemail', 'adressecourriel'),
    'address': (
        'address',
        'adresse',
        'adressecomplete',
        'fulladdress',
        'streetaddress',
        'addressesaddress1',
        'street',
        'rue',
    ),
    'city': ('city', 'ville', 'villes', 'municipalite'),
    'postal_code': ('postalcode', 'codepostal', 'postcode', 'addresseszip'),
}
FIRST_NAMES = ('firstname', 'prenom', 'givenname')
LAST_NAMES = ('lastname', 'nom', 'familyname', 'surname')
ISOLATION_COLUMNS = {
    **COORDINATE_COLUMNS,
    'phone': (
        'phone',
        'phonenumber',
        'telephone',
        'tel',
        'numero',
        'numerodetelephone',
        'mobile',
        'mobilephone',
        'cell',
        'cellphone',
    ),
    'name': ('name', 'fullname', 'nomcomplet', 'nometprenom', 'contactname'),
    'first_name': FIRST_NAMES,
    'last_name': LAST_NAMES,
    'reference': ('reference', 'externalid', 'referenceexterne'),
}


def header_key(value):
    text = unicodedata.normalize('NFKD', str(value)).encode('ascii', 'ignore').decode().lower()
    return re.sub('[^a-z0-9]', '', text)


def suggested_columns(headers):
    result = {}
    for field, aliases in ISOLATION_COLUMNS.items():
        candidates = [header for header in headers if header_key(header) in aliases]
        if len(candidates) == 1:
            result[field] = candidates[0]
    if 'name' in result:
        result.pop('first_name', None)
        result.pop('last_name', None)
    return result


def has_explicit_columns(mapping):
    """Old batches only chose phone, name and reference and retain legacy name fallback."""
    return any(field in mapping for field in (*COORDINATE_COLUMNS, 'first_name', 'last_name'))


def selected_value(row, column):
    return str(row.get(column, '') or '').strip() if column else ''
