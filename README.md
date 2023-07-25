# SIPB Matrix

SIPB Matrix (codename Uplink) is SIPB's effort to bring the [Matrix](https://matrix.org) network to MIT, providing not just another hosted homeserver, but a practical way to communicate that works with the school's existing social dynamics and ecosystem (class group chats, Moira lists, etc), aiming to reduce the usage of proprietary alternatives such as Facebook Messenger, and exclusionary and proprietary alternatives such as iMessage.

## What's in this repo?

* `server`: a view into the config files of our homeserver

* `moira_interface` (deprecated): first attempt to build a Moira integration. It uses a deprecated Moira API.

* `uplink_synapse_module`: custom code to interface with Synapse (also WIP, may move to another repo)

## What other repos are part of this project?

* [matrix-zephyr-bridge](https://github.com/sipb/matrix-zephyr-bridge): A bridge with Zephyr, an old messaging protocol still used by SIPB alumni

* [mattermost-to-matrix-migration](https://github.com/gabrc52/mattermost-to-matrix-migration): A backfill bridge with Mattermost, in an attempt to move SIPB to Matrix while preserving full compatibility with Mattermost.

* [uplink-moira-bot](https://github.com/sipb/uplink-moira-bot): Another deprecated attempt to build a Moira integration. It uses the deprecated Moira API we are not supposed to use.

* [moira-rest-api](https://github.com/gabrc52/moira-rest-api): A new full RESTful API to interact with Moira, useful for SIPB projects or projects at MIT in general.
