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

`skip_prefixes` is to avoid welcoming ghost (bridged) users. Otherwise, this plugin would cause app services to be ratelimited(!)

```yaml
modules:
    - module: uplink_synapse_module.UplinkFirstLoginModule
        config:
            skip_prefixes:
                - "@_mattermost_"
                - "@_zephyr_"
            plain_text: |
                Hello, world. You can use the YAML syntax...
                ...to add a multiline string here.
            html: "..." # HTML version of the message, set to null to only send plain text
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
            enable: true # or false, if you don't want to use the people api
            client_id: client_id_goes_here
            client_secret: client_secret_goes_here
        # optional - block prefixes to include from search results
        blocked_prefixes:
            - mattermost_
            - _zephyr_
        blacklisted_homeservers:
            - uplink.mit.edu
```
