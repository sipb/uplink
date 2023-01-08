# see:
# https://nickx.hu/posts/2020-07-13-matrix-synapse-shibboleth-saml.html
# https://pysaml2.readthedocs.io/en/latest/howto/config.html#attribute-map-dir

# If this can be any Python code, then let us compute the inverse instead of rewriting

__map_to = {
    'eppn': 'urn:oid:1.3.6.1.4.1.5923.1.1.1.6',
    'affiliation': 'urn:oid:1.3.6.1.4.1.5923.1.1.1.9',
    'cn': 'urn:oid:2.5.4.3',
    'sn': 'urn:oid:2.5.4.4',
    'givenName': 'urn:oid:2.5.4.42',
    'email': 'urn:oid:0.9.2342.19200300.100.1.3',
    'displayName': 'urn:oid:2.16.840.1.113730.3.1.241',
    'memberOf': 'urn:oid:1.2.840.113556.1.2.102',
    'entitlement': 'urn:oid:1.3.6.1.4.1.5923.1.1.1.7',
    'uid': 'urn:oid:1.3.6.1.4.1.5923.1.1.1.6',
}

MAP = {
    'identifier': 'urn:oasis:names:tc:SAML:2.0:attrname-format:uri',
    'to': __map_to,
    'fro': {v:k for k,v in __map_to.items()},
}
