# Copyright 2023 Max Planck Institute for Software Systems, and
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

import random
import itertools
import simbricks.orchestration.experiments as exp
import simbricks.orchestration.nodeconfig as node
import simbricks.orchestration.simulators as sim
import simbricks.orchestration.e2e_components as e2e
from simbricks.orchestration import e2e_partition
from simbricks.orchestration.simulator_utils import create_tcp_cong_hosts
from simbricks.orchestration.e2e_topologies import (HomaTopology, add_homa_bg)

types_of_protocol = ['tcp', 'homa']
n_remotes_per_sender = [4, 8, 16]
partitions = e2e_partition.hier_partitions_homa(HomaTopology()).keys()
sync_factors = [1.0, 0.5, 0.25, 0.1]
network_loads = ['0.5', '0.8']

initial_credit = '7'
total_prio_bands = '8'
unsched_prio_bands = '2'
inbnd_rtx_timeout = '1ms'
outbound_rtx_timeout = '10ms'
start_time = '3s'
stop_time = '23s'
application_runtime = 2 # in seconds
msg_size_dist_file = ''

jitter = e2e.E2ENs3ConstantRandomVariable()
jitter.constant = 0.0

options = {
    'ns3::TcpSocket::SegmentSize': 1448,
    'ns3::TcpSocket::SndBufSize': 29960000,
    'ns3::TcpSocket::RcvBufSize': 29960000,
    'ns3::TcpSocket::ConnTimeout': '100ms',
    'ns3::Ipv4GlobalRouting::RandomEcmpRouting': '1',
    'ns3::Ipv4L3Protocol::MayFragment': 'false',
    'ns3::HomaL4Protocol::RttPackets': initial_credit,
    'ns3::HomaL4Protocol::NumTotalPrioBands': total_prio_bands,
    'ns3::HomaL4Protocol::NumUnschedPrioBands': unsched_prio_bands,
    'ns3::HomaL4Protocol::InbndRtxTimeout': inbnd_rtx_timeout,
    'ns3::HomaL4Protocol::OutbndRtxTimeout': outbound_rtx_timeout,
    'ns3::ArpCache::PendingQueueSize': 1024,
    'ns3::ArpL3Protocol::RequestJitter': jitter.get_config(),
}

experiments = []

for proto, N, p_id, sf, nl in itertools.product(types_of_protocol, n_remotes_per_sender, partitions, sync_factors, network_loads):
    random.seed(42) # make sure remotes are selected the same way
    e = exp.Experiment(f'homa_ns3_{proto}_{N}_{p_id}_{sf}_{nl}')

    if proto == 'homa':
        AppClass = e2e.E2EMsgGenApplication
    elif proto == 'tcp':
        AppClass = e2e.E2EMsgGenApplicationTCP
    else:
        raise NameError(f'Unkown {proto} in types_of_protocol')

    start_time = f'{0.1 + N * 0.001 + 3}s'
    stop_time = f'{0.1 + N * 0.001 + 3 + application_runtime}s'
    global_stop = f'{0.1 + N * 0.001 + 3 + application_runtime + 2}s'

    topology = HomaTopology(
        pfifo_num_bands=total_prio_bands,
        network_load=nl,
        start_time=start_time,
        stop_time=stop_time,
        msg_size_dist_file=msg_size_dist_file,
        n_remotes=N
    )

    topology.add_homa_hosts()
    topology.add_homa_app(AppClass)

    partition = e2e_partition.hier_partitions_homa(topology)[p_id]
    nets = e2e_partition.instantiate_partition(topology, partition, sf)
    with open(f'out/{e.name}.dot', 'w') as f:
        dot = e2e_partition.dot_topology(topology, partition)
        f.write(dot)

    for (i, net) in enumerate(nets):
        net.opt = ' '.join([f'--{o[0]}={o[1]}' for o in options.items()])
        net.e2e_global.stop_time = global_stop
        net.e2e_global.progress = f'100ms,{global_stop}'

        # add probes for homa
        probe = e2e.E2ETracer('homa_traces', 'MsgBeginFinish')
        probe.file = f'{proto}_trace_{nl}_{i}.tr'
        net.add_component(probe)

        net.wait = True
        e.add_network(net)
        net.init_network()

    experiments.append(e)
