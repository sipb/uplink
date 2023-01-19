import json

# TODO: migrate this to SQL or something like https://github.com/turicas/pybitcask
# everything is O(N), and idk performat that would be in practice
# or ask what's the best way somewhere

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
    
