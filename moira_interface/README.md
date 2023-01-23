# Moira Matrix integration

This is a Matrix bot that integrates with MIT mailing lists

You need a config file `config.json` with the following contents:

```json
{
    "homeserver": "https://uplink.mit.edu",
    "server_name": "uplink.mit.edu",
    "username": "@moira-bot:uplink.mit.edu",
    "token": "your-precious-token-goes-here",
    "id_server": "matrix.org",
    "power_levels": {
        "bot": 101,
        "owner": 100,
        "memacl": 50
    }
}
```

Also create `db.json` with the following contents:

```json
{
    "lists": []
}
```

NOTE: Before running the bot, you must look at the identity server terms at 
https://matrix.org/_matrix/identity/v2/terms and accept them by running the
`accept_identity_server_terms` function, possibly adjusting the URL if needed