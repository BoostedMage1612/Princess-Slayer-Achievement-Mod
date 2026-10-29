"""Match the executing compiled menu without running game expressions."""
import hashlib
import json
import posixpath
from collections import defaultdict


def normalized_file(filename):
    path = posixpath.normpath(str(filename or '').replace('\\', '/')).casefold()
    if '/game/' in path:
        path = path.rsplit('/game/', 1)[1]
    elif path.startswith('game/'):
        path = path[5:]
    if path.endswith('.rpyc'):
        path = path[:-1]
    return path


def native_key(name):
    if isinstance(name, (tuple, list)) and name:
        return (normalized_file(name[0]),) + tuple(name[1:])
    return name


def fingerprint(items):
    values = [[str(label), str(condition), block is not None]
              for label, condition, block in items]
    return hashlib.sha256(json.dumps(values, ensure_ascii=False,
                                    separators=(',', ':')).encode('utf-8')).hexdigest()


class MenuLocator:
    def __init__(self, nodes, runtime):
        self.nodes = {pc: n for pc, n in nodes.items() if n['op'] == 'menu'}
        self.runtime = {int(pc): entry for pc, entry in runtime.items()}
        self.locations = {}
        self.names = defaultdict(list)
        self.signatures = defaultdict(list)
        for pc, n in self.nodes.items():
            filename = normalized_file(n['file'])
            self.locations[filename, n['line']] = pc
            entry = self.runtime.get(pc)
            if entry:
                self.names[native_key(entry['name'])].append(pc)
                self.signatures[filename, entry['signature']].append(pc)

    def locate(self, api):
        info = {'method': 'unmatched'}
        try:
            filename, line = api.get_filename_line()
        except Exception:
            filename, line = '', 0
        path = normalized_file(filename)
        info.update(file=path, line=line)
        node = None
        try:
            # `store.renpy` is renpy.exports in 8.0.3; its `renpy` attribute
            # points to the engine. Test adapters may expose game directly.
            engine = api if hasattr(api, 'game') else api.renpy
            node = engine.game.script.namemap.get(engine.game.context().current)
        except (AttributeError, TypeError):
            pass
        if node is not None:
            info['node_type'] = type(node).__name__
            if type(node).__name__ != 'Menu':
                info['reason'] = 'current statement is not a story menu'
                return None, info
            path = normalized_file(node.filename)
            line = node.linenumber
            signature = fingerprint(node.items)
            info.update(file=path, line=line, signature=signature)
            # A compiled identity plus ALL captions, conditions and branch slots
            # is stronger than a debug filename/line pair. Never match one caption.
            candidates = self.names.get(native_key(node.name), [])
            candidates = [pc for pc in candidates
                          if self.runtime[pc]['signature'] == signature]
            if len(candidates) == 1:
                info['method'] = 'compiled_menu'
                return candidates[0], info
            pc = self.locations.get((path, line))
            if pc is not None and self.runtime.get(pc, {}).get('signature') == signature:
                info['method'] = 'verified_location'
                return pc, info
            candidates = self.signatures.get((path, signature), [])
            if len(candidates) == 1:
                info['method'] = 'unique_menu_signature'
                return candidates[0], info
            info['reason'] = ('ambiguous menu signature' if candidates
                              else 'compiled menu does not match the checked map')
            return None, info
        # Compatibility fallback for engines exposing only the documented API.
        pc = self.locations.get((path, line))
        if pc is not None:
            info['method'] = 'source_location'
        else:
            info['reason'] = 'no matching menu location'
        return pc, info
