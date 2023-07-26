import json

# TODO: migrate this to SQL or something like https://github.com/turicas/pybitcask
# everything is O(N), and idk performat that would be in practice
# or ask what's the best way somewhere

# well, if you really need a database, here is a novel idea: use Matrix itself as the database
# after all it is a big DAG of events and you can query for specific state events
# so in the end, maaaaaaaybe this might do the trick instead, using one room as database

# Uhh https://spec.matrix.org/latest/
# State events [...] describe updates to a given piece of persistent information (‘state’) related to a room, such as the room’s name, topic, membership, participating servers, etc. State is modelled as a lookup table of key/value pairs per room, with each key being a tuple of state_key and event type. Each state event updates the value of a given key."
# All the Moira info can be a state event. Whenever settings are updated it can be changed

class Database:
    """
    Basically a persistent dict that (for now) writes and reads from a JSON file
    """

    def __init__(self, filename='db.json'):
        self.filename = filename

    def _get_dict(self):
        with open('db.json', 'r') as f:
            d = json.load(f)
        return d

    def _save_dict(self, d):
        with open('db.json', 'w') as f:
            json.dump(d, f)
    
    def __getitem__(self, key):
        return self._get_dict()[key]
    
    def __setitem__(self, key, val):
        d = self._get_dict()
        d[key] = val
        self._save_dict(d)
    
    def __delitem__(self, key):
        d = self._get_dict()
        del d[key]
        self._save_dict(d)

    def append(self, key, val):
        d = self._get_dict()
        d[key].append(val)
        self._save_dict(d)
    
