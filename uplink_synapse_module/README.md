# Synapse plugins

To install them, you need to install this package on Synapse's venv:

```
# source /opt/venvs/matrix-synapse/bin/activate
# pip install .
```

You also need to edit `modules:` in your Synapse config.

## Welcome message on first login

Add under `modules:` in your Synapse config

See the following configuration options.

You can include `{displayname}` and `{mxid}` and they will be replaced with the display name and mxid of the user who just signed up, respectively, using the Python `str.format` function.

```yaml
modules:
    - module: uplink_synapse_module.UplinkFirstLoginModule
        config:
            html: |
                Hello, world. You can use the YAML syntax...
                ...to add a multiline string here.
            plain_text: "..." # Plain text version of the message, set to null to only send plain text
    # ...
```

## People API

See the following configuration options.

```yaml
modules:
    # ...
    - module: uplink_synapse_module.PeopleApiSynapseService
    config:
        people_api:
            client_id: client_id_goes_here
            client_secret: client_secret_goes_here
```
