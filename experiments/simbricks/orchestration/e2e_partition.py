# Copyright 2024 Max Planck Institute for Software Systems, and
# National University of Singapore
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

# Allow own class to be used as type for a method's argument
from __future__ import annotations

import collections
import typing as tp
from enum import Enum
import metis

import simbricks.orchestration.simulators as sim
import simbricks.orchestration.e2e_components as comps
import simbricks.orchestration.e2e_topologies as topos
from simbricks.orchestration.e2e_helpers import E2ELinkAssigner, E2ELinkType

# maps components to consecutive ids and back, ensuring each id is only assigned
# once.
class IDMap(object):
    def __init__(self):
        self.dict = {}
        self.l = []
        self.next = 0

    def to_id(self, n):
        if n in self.dict:
            return self.dict[n]
        else:
            k = self.next
            self.next += 1
            self.dict[n] = k
            self.l.append(n)
            return k

    def from_id(self, i):
        return self.l[i]

    def items(self):
        return self.dict.items()

# Split the topology into N networks, return E2ENetwork instances
def partition(topology, N):
    adjlists = collections.defaultdict(tuple)
    edges = []
    idmap = IDMap()
    for l in topology.get_links():
        l_i = idmap.to_id(l.left_node)
        r_i = idmap.to_id(l.right_node)
        adjlists[l_i] += (r_i,)
        adjlists[r_i] += (l_i,)
        edges.append((l_i, r_i))
    for sw in topology.get_switches():
        for h in sw.components:
            l_i = idmap.to_id(sw)
            r_i = idmap.to_id(h)
            adjlists[l_i] += (r_i,)
            adjlists[r_i] += (l_i,)
            edges.append((l_i, r_i))

    max_node = max(adjlists.keys())
    graph = []
    for i in range(0, max_node + 1):
        graph.append(adjlists[i])

    if N == 1:
        # metis does not like N=1 :-)
        parts = [0] * (max_node + 1)
    else:
        (edgecuts, parts) = metis.part_graph(graph, N)

    node_partitions = {}
    for (i,p) in enumerate(parts):
        if p not in node_partitions:
            node_partitions[p] = []
        node_partitions[p].append(i)

    # For debugging: print out dot representation of partition
    #print('graph R {')
    #for p in sorted(node_partitions.keys()):
    #    print(f'subgraph cluster{p} {{')
    #    for n_i in node_partitions[p]:
    #      n = idmap.from_id(n_i)
    #      print(f'n{n_i} [label="{n.id}"];')
    #    print('}')
    #for (s,d) in edges:
    #    print(f'n{s} -- n{d};')
    #print('}')


    # create the networks
    networks = []
    for p in sorted(node_partitions.keys()):
        net = sim.NS3E2ENet()
        net.name = f'netpart_{p}'
        networks.append(net)

    # add the switches
    for sw in topology.get_switches():
        p = parts[idmap.to_id(sw)]
        net = networks[p]
        net.add_component(sw)

    # add the links
    for l in topology.get_links():
        l_i = idmap.to_id(l.left_node)
        l_p = parts[l_i]
        r_i = idmap.to_id(l.right_node)
        r_p = parts[r_i]
        if l_p == r_p:
            # both end in the same partiton, just add the link
            networks[l_p].add_component(l)
        else:
            # make sure that connections always go in one direction, so there is
            # a topological order for dependencies when launching
            if l_p < r_p:
              lst_p = l_p
              lst = l.left_node
              con_p = r_p
              con = l.right_node
            else:
              lst_p = r_p
              lst = l.right_node
              con_p = l_p
              con = l.left_node

            lst_a = comps.E2ESimbricksNetworkNicIf(f'crossL_{l_i}_{r_i}')
            lst_a.eth_latency = f'{l.delay}'
            lst_a.sync_delay = f'{l.delay}'
            lst_a.simbricks_component = networks[con_p]
            lst.add_component(lst_a)

            con_a = comps.E2ESimbricksNetworkNetIf(f'crossC_{l_i}_{r_i}')
            con_a.eth_latency = f'{l.delay}'
            con_a.sync_delay = f'{l.delay}'
            con_a.simbricks_component = networks[lst_p]
            con.add_component(con_a)

    return networks
