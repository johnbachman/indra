from collections import deque

import networkx as nx
import networkx.algorithms.simple_paths as simple_paths
from networkx.classes.reportviews import NodeView, OutEdgeView, \
    OutMultiEdgeView

from indra.explanation.pathfinding_util import signed_nodes_to_signed_edge


# Copy from networkx.algorithms.simple_paths
# Added ignore_nodes and ignore_edges arguments
def shortest_simple_paths(G, source, target, weight=None, ignore_nodes=None,
                          ignore_edges=None):
    """Generate all simple paths in the graph G from source to target,
       starting from shortest ones.

    A simple path is a path with no repeated nodes.

    If a weighted shortest path search is to be used, no negative weights
    are allowed.

    Parameters
    ----------
    G : NetworkX graph

    source : node
       Starting node for path

    target : node
       Ending node for path

    weight : string
        Name of the edge attribute to be used as a weight. If None all
        edges are considered to have unit weight. Default value None.

    ignore_nodes : container of nodes
       nodes to ignore, optional

    ignore_edges : container of edges
       edges to ignore, optional

    Returns
    -------
    path_generator: generator
       A generator that produces lists of simple paths, in order from
       shortest to longest.

    Raises
    ------
    NetworkXNoPath
       If no path exists between source and target.

    NetworkXError
       If source or target nodes are not in the input graph.

    NetworkXNotImplemented
       If the input graph is a Multi[Di]Graph.

    Examples
    --------

    >>> G = nx.cycle_graph(7)
    >>> paths = list(nx.shortest_simple_paths(G, 0, 3))
    >>> print(paths)
    [[0, 1, 2, 3], [0, 6, 5, 4, 3]]

    You can use this function to efficiently compute the k shortest/best
    paths between two nodes.

    >>> from itertools import islice
    >>> def k_shortest_paths(G, source, target, k, weight=None):
    ...     return list(islice(nx.shortest_simple_paths(G, source, target,
    ...         weight=weight), k))
    >>> for path in k_shortest_paths(G, 0, 3, 2):
    ...     print(path)
    [0, 1, 2, 3]
    [0, 6, 5, 4, 3]

    Notes
    -----
    This procedure is based on algorithm by Jin Y. Yen [1]_.  Finding
    the first $K$ paths requires $O(KN^3)$ operations.

    See Also
    --------
    all_shortest_paths
    shortest_path
    all_simple_paths

    References
    ----------
    .. [1] Jin Y. Yen, "Finding the K Shortest Loopless Paths in a
       Network", Management Science, Vol. 17, No. 11, Theory Series
       (Jul., 1971), pp. 712-716.

    """
    if source not in G:
        s = source[0] if isinstance(source, tuple) else source
        raise nx.NodeNotFound('source node %s not in graph' % s)

    if target not in G:
        t = target[0] if isinstance(target, tuple) else target
        raise nx.NodeNotFound('target node %s not in graph' % t)

    if weight is None:
        length_func = len
        shortest_path_func = simple_paths._bidirectional_shortest_path
    else:
        def length_func(path):
            return sum(G.adj[u][v][weight] for (u, v) in zip(path, path[1:]))
        shortest_path_func = simple_paths._bidirectional_dijkstra

    culled_ignored_nodes = set() if ignore_nodes is None else set(ignore_nodes)
    culled_ignored_edges = set() if ignore_edges is None else set(ignore_edges)
    listA = list()
    listB = simple_paths.PathBuffer()
    prev_path = None
    while True:
        cur_ignore_nodes = culled_ignored_nodes.copy()
        cur_ignore_edges = culled_ignored_edges.copy()
        if not prev_path:
            length, path = shortest_path_func(G, source, target, weight=weight,
                                              ignore_nodes=cur_ignore_nodes,
                                              ignore_edges=cur_ignore_edges)
            listB.push(length, path)
        else:
            for i in range(1, len(prev_path)):
                root = prev_path[:i]
                root_length = length_func(root)
                for path in listA:
                    if path[:i] == root:
                        cur_ignore_edges.add((path[i - 1], path[i]))
                try:
                    length, spur = shortest_path_func(
                        G, root[-1], target, ignore_nodes=cur_ignore_nodes,
                        ignore_edges=cur_ignore_edges, weight=weight)
                    path = root[:-1] + spur
                    listB.push(root_length + length, path)
                except nx.NetworkXNoPath:
                    pass
                cur_ignore_nodes.add(root[-1])
        if listB:
            path = listB.pop()
            rcvd_ignore_values = yield path
            if rcvd_ignore_values is not None:
                culled_ignored_nodes = culled_ignored_nodes.union(
                    rcvd_ignore_values[0])
                culled_ignored_edges = culled_ignored_edges.union(
                    rcvd_ignore_values[1])
            listA.append(path)
            prev_path = path
        else:
            break


def get_sorted_neighbors(G, node, reverse, g_edges):
    # better sorted key
    """Sort by aggregated belief per edge"""
    neighbors = G.predecessors(node) if reverse else G.successors(node)
    # Check signed node
    if isinstance(node, tuple):
        if reverse:
            return sorted(
                neighbors,
                key=lambda n:
                    g_edges[signed_nodes_to_signed_edge(n, node)]['belief'],
                reverse=True
            )
        else:
            return sorted(
                neighbors,
                key=lambda n:
                    g_edges[signed_nodes_to_signed_edge(node, n)]['belief'],
                reverse=True)

    else:
        if reverse:
            return sorted(neighbors,
                          key=lambda n: g_edges[(n, node)]['belief'],
                          reverse=True)
        else:
            return sorted(neighbors,
                          key=lambda n: g_edges[(node, n)]['belief'],
                          reverse=True)


# Implementation inspired by networkx's
# networkx.algorithms.traversal.breadth_first_search::generic_bfs_edges
def bfs_search(g, source_node, g_nodes=None, g_edges=None, reverse=False,
               depth_limit=2, path_limit=None, max_per_node=5,
               node_filter=None, node_blacklist=None, terminal_ns=None,
               sign=None, **kwargs):
    """Do breadth first search from a given node and yield paths

    Parameters
    ----------
    g : nx.Digraph
        An nx.DiGraph to search in. Can also be a signed node graph.
    source_node : node
        Node in the graph to start from.
    g_nodes : nx.classes.reportviews.nodesNodeView
        The nodes property to look up nodes from. Set this if the node
        attribute 'ns' needs to be looked up from another graph object than
        the one provided as `g`. Default: g.nodes
    g_edges : nx.classes.reportviews.OutMultiEdgeView|OutEdgeView
        The edges property to look up edges and their data from. Set this if
        the edge beliefs needs to be looked up from another grapth object
        than `g`. Default: d.edges
    reverse : bool
        If True go upstream from source, otherwise go downstream. Default:
        False.
    depth_limit : int
        Stop when all paths with this many edges have been found. Default: 2.
    path_limit : int
        The maximum number of paths to return. Default: no limit.
    max_per_node : int
        The maximum number of paths to yield per parent node. If 1 is
        chosen, the search only goes down to the leaf node of its first
        encountered branch. Default: 5
    node_filter : list[str]
        The allowed namespaces (node attribute 'ns') for the nodes in the
        path
    node_blacklist : set[node]
        A set of nodes to ignore. Default: None.
    terminal_ns : list[str]
        Force a path to terminate when any of the namespaces in this list
        are encountered.
    sign : int
        If set, defines the search to be a signed search. Default: None.

    Yields
    ------
    path : tuple(node)
        Paths in the bfs search starting from `source`.
    """
    int_plus = 0
    int_minus = 1
    g_nodes = g.nodes if g_nodes is None else g_nodes
    g_edges = g.edges if g_edges is None else g_edges
    if not isinstance(g_nodes, NodeView):
        raise ValueError('Provided object for g_nodes is not a valid '
                         'NodeView object')
    if not isinstance(g_edges, (OutEdgeView, OutMultiEdgeView)):
        raise ValueError('Provided object for g_edges is not a valid '
                         'OutEdgeView or OutMultiEdgeView object')

    queue = deque([(source_node,)])
    visited = ({source_node}).union(node_blacklist) \
        if node_blacklist else {source_node}
    yielded_paths = 0
    while queue:
        cur_path = queue.popleft()
        last_node = cur_path[-1]
        node_name = last_node[0] if isinstance(last_node, tuple) else \
            last_node

        # if last node is in terminal_ns, continue to next path
        if terminal_ns and g_nodes[node_name]['ns'].lower() in terminal_ns:
            # Check correct leaf sign for signed search
            continue

        sorted_neighbors = get_sorted_neighbors(G=g, node=last_node,
                                                reverse=reverse,
                                                g_edges=g_edges)

        yielded_neighbors = 0
        # for neighb in neighbors:
        for neighb in sorted_neighbors:
            neig_name = neighb[0] if isinstance(neighb, tuple) else neighb

            # Check cycles
            if sign is not None:
                # Avoid signed paths ending up on the opposite sign of the
                # same node
                if (neig_name, int_minus) in cur_path or \
                        (neig_name, int_plus) in cur_path:
                    continue
            elif neighb in visited:
                continue

            # Check namespace
            if node_filter and len(node_filter) > 0:
                if g_nodes[neig_name]['ns'].lower() not in node_filter:
                    continue

            # Add to visited nodes and create new path
            visited.add(neighb)
            new_path = cur_path + (neighb,)

            # Check yield and break conditions
            if len(new_path) > depth_limit + 1:
                continue
            else:
                # Yield newest path and recieve new ignore values

                # Signed search yield
                if sign is not None:
                    if reverse:
                        # Upstream signed search should not end in negative
                        # node
                        if new_path[-1][1] == int_minus:
                            ign_vals = None
                            pass
                        else:
                            ign_vals = yield new_path
                            yielded_paths += 1
                            yielded_neighbors += 1

                    else:
                        # Downstream signed search has to end on node with
                        # requested sign
                        if new_path[-1][1] != sign:
                            ign_vals = None
                            pass
                        else:
                            ign_vals = yield new_path
                            yielded_paths += 1
                            yielded_neighbors += 1

                # Unsigned search
                else:
                    ign_vals = yield new_path
                    yielded_paths += 1
                    yielded_neighbors += 1

                # If new ignore nodes are recieved, update set
                if ign_vals is not None:
                    ign_nodes, ign_edges = ign_vals
                    visited.update(ign_nodes)

                # Check max paths reached, no need to add to queue
                if path_limit and yielded_paths >= path_limit:
                    break

            # Append yielded path
            queue.append(new_path)

            # Check if we've visited enough neighbors
            # Todo: add all neighbors to 'visited' and add all skipped
            #  paths to queue? Currently only yielded paths are
            #  investigated deeper
            if max_per_node and yielded_neighbors >= max_per_node:
                break

        # Check path limit again to catch the inner break for path_limit
        if path_limit and yielded_paths >= path_limit:
            break
