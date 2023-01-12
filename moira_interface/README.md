# Moira Matrix integration

This is a Matrix bot that integrates with MIT mailing lists

You need a config file with the following contents:

```json
{
    "homeserver": "https://uplink.mit.edu",
    "server_name": "uplink.mit.edu",
    "username": "@moira-bot:uplink.mit.edu",
    "token": "your-precious-token-goes-here",
    "id_server": "matrix.org"
}
```

NOTE: Before running the bot, you must look at the identity server terms at 
https://matrix.org/_matrix/identity/v2/terms and accept them by running the
`accept_identity_server_terms` function, possibly adjusting the URL if needed

TODO: would be good to use `poetry` or something else for dependency management