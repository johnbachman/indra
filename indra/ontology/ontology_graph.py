import logging
import networkx
from collections import deque

logger = logging.getLogger(__name__)


class IndraOntology(networkx.DiGraph):
    def __init__(self):
        super().__init__()
        self.name_to_grounding = {}

    def _check_path(self, ns1, id1, ns2, id2, edge_types):
        try:
            target = (ns2, id2)
            if target in self._transitive_rel(ns1, id1, self.child_rel,
                                              edge_types, target):
                return True
            else:
                return False
        # This typically happens if the node is missing from
        # the graph. Is there a more specific error type?
        except networkx.NetworkXError:
            return False

    @staticmethod
    def get_ns_id(node):
        return tuple(node.split(':', maxsplit=1))

    @staticmethod
    def get_ns(node):
        return IndraOntology.get_ns_id(node)[0]

    @staticmethod
    def get_id(node):
        return IndraOntology.get_ns_id(node)[1]

    def isrel(self, ns1, id1, ns2, id2, rels):
        return self._check_path(ns1, id1, ns2, id2, rels)

    def isa(self, ns1, id1, ns2, id2):
        return self.isrel(ns1, id1, ns2, id2, rels={'isa'})

    def partof(self, ns1, id1, ns2, id2):
        return self.isrel(ns1, id1, ns2, id2, rels={'partof'})

    def isa_or_partof(self, ns1, id1, ns2, id2):
        return self.isrel(ns1, id1, ns2, id2, rels={'isa', 'partof'})

    def maps_to(self, ns1, id1, ns2, id2):
        return self._check_path(ns1, id1, ns2, id2, {'xref'})

    def map_to(self, ns1, id1, ns2):
        targets = [target for target in
                   self.descendants_rel(ns1, id1, {'xref'})
                   if target[0] == ns2]
        if len(targets) == 1:
            return targets[0]
        return None

    def _transitive_rel(self, ns, id, rel_fun, rel_types, target=None):
        source = (ns, id)
        visited = {source}
        queue = deque([(source,
                        rel_fun(*source, rel_types))])
        while queue:
            parent, children = queue[0]
            try:
                child = next(children)
                if target and child == target:
                    return [target]
                if child not in visited:
                    visited.add(child)
                    queue.append((child,
                                  rel_fun(*child, rel_types)))
            except networkx.NetworkXError as e:
                logger.debug(e)
                return []
            except StopIteration:
                queue.popleft()
        return list(visited - set(source))

    def descendants_rel(self, ns, id, rel_types):
        return self._transitive_rel(ns, id, self.child_rel, rel_types)

    def ancestors_rel(self, ns, id, rel_types):
        return self._transitive_rel(ns, id, self.parent_rel, rel_types)

    def child_rel(self, ns, id, rel_types):
        source = label(ns, id)
        for target in self.successors(source):
            if self.edges[source, target]['type'] in rel_types:
                yield self.get_ns_id(target)

    def parent_rel(self, ns, id, rel_types):
        target = label(ns, id)
        for source in self.predecessors(target):
            if self.edges[source, target]['type'] in rel_types:
                yield self.get_ns_id(source)

    def get_children(self, ns, id):
        return self.ancestors_rel(ns, id, {'isa', 'partof'})

    def get_parents(self, ns, id):
        return self.descendants_rel(ns, id, {'isa', 'partof'})

    def get_top_level_parents(self, ns, id):
        parents = self.get_parents(ns, id)
        return [p for p in parents if not self.get_parents(*p)]

    def get_mappings(self, ns, id):
        return self.descendants_rel(ns, id, {'xref'})

    def get_name(self, ns, id):
        return self.get_node_property(ns, id, property='name')

    def get_polarity(self, ns, id):
        return self.get_node_property(ns, id, property='polarity')

    def get_node_property(self, ns, id, property):
        try:
            return self.nodes[label(ns, id)][property]
        except KeyError:
            return None

    def is_opposite(self, ns1, id1, ns2, id2):
        return self._check_path(ns1, id1, ns2, id2, {'is_opposite'})

    def get_id_from_name(self, ns, name):
        if not self.name_to_grounding:
            self._build_name_lookup()
        return self.name_to_grounding.get((ns, name))

    def _build_name_lookup(self):
        self.name_to_grounding = {
            (self.get_ns(node), data['name']): self.get_ns_id(node)
            for node, data in self.nodes(data=True)
            if 'name' in data
        }

    def nodes_from_suffix(self, suffix):
        return [node for node in self.nodes
                if node.endswith(suffix)]

def label(ns, id):
    return '%s:%s' % (ns, id)


