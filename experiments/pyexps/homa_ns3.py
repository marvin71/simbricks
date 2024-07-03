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
import typing as tp
import simbricks.orchestration.experiments as exp
import simbricks.orchestration.simulators as sim
import simbricks.orchestration.e2e_components as e2e
from simbricks.orchestration import e2e_partition
from simbricks.orchestration.e2e_topologies import HomaTopology

types_of_protocol_fg = ['homa']
types_of_protocol_bg = ['tcp', 'homa']
n_remotes_per_sender = [4, 8, 16]
partitions = e2e_partition.hier_partitions_homa(HomaTopology()).keys()
sync_factors = [1.0, 0.5, 0.25, 0.1]
network_loads = ['0.5', '0.8']

n_racks = 9
h_per_rack = 16
n_hosts = n_racks * h_per_rack
n_foreground_hosts = 16

initial_credit = '7'
total_prio_bands = '8'
unsched_prio_bands = '2'
inbnd_rtx_timeout = '100s'
outbound_rtx_timeout = '100s'
application_runtime = 10 # in seconds
fadeout_time = 0 # in seconds
msg_size_dist_file = ''

jitter = e2e.E2ENs3ConstantRandomVariable()
jitter.constant = 0.0

options = {
    'ns3::TcpSocket::SegmentSize': 1448,
    'ns3::TcpSocket::SndBufSize': 29960000,
    'ns3::TcpSocket::RcvBufSize': 29960000,
    'ns3::TcpSocket::ConnTimeout': '100ms',
    'ns3::TcpSocketBase::ClockGranularity': '1ms',
    'ns3::TcpSocketBase::MinRto': '200ms',
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

random.seed(42) # make sure remotes are selected the same way

foreground_hosts = random.sample(range(n_hosts), n_foreground_hosts)
background_hosts = [host for host in range(n_hosts) if host not in foreground_hosts]

def GetApp(app_type: str) -> e2e.E2EApplication:
    if app_type == 'homa':
        return e2e.E2EMsgGenApplication
    elif app_type == 'tcp':
        return e2e.E2EMsgGenApplicationTCP
    else:
        raise NameError(f'Unkown {app_type} in types_of_protocol')

for proto_fg, proto_bg, N, p_id, sf, nl in itertools.product(types_of_protocol_fg, types_of_protocol_bg, n_remotes_per_sender, partitions, sync_factors, network_loads):
    e = exp.Experiment(f'homa_ns3_{proto_fg}_{proto_bg}_{N}_{p_id}_{sf}_{nl}')

    start_time = 0.1 + N * 0.001 + 3
    stop_time = start_time + application_runtime + 1
    global_stop = stop_time + fadeout_time

    topology = HomaTopology(
        pfifo_num_bands=total_prio_bands,
        network_load=nl,
        start_time=f'{start_time}s',
        stop_time=f'{stop_time}s',
        msg_size_dist_file=msg_size_dist_file,
        n_remotes=N,
        n_agg_racks=n_racks,
        h_per_rack=h_per_rack
    )

    topology.add_homa_hosts()

    topology.print_ip_addresses(foreground_hosts)

    # start homa app 1s later, so that tcp sockets can connect
    if proto_fg == 'homa':
        topology.params['start_time'] = f'{start_time + 1}s'
    topology.add_homa_app(GetApp(proto_fg), foreground_hosts,
                          n_foreground_hosts - 1)
    topology.params['start_time'] = f'{start_time}s'
    if proto_bg == 'homa':
        topology.params['start_time'] = f'{start_time + 1}s'
    topology.add_homa_app(GetApp(proto_bg), background_hosts, N)

    partition = e2e_partition.hier_partitions_homa(topology)[p_id]
    nets = e2e_partition.instantiate_partition(topology, partition, sf)
    with open(f'out/{e.name}.dot', 'w') as f:
        dot = e2e_partition.dot_topology(topology, partition)
        f.write(dot)

    for (i, net) in enumerate(nets):
        net.opt = ' '.join([f'--{o[0]}={o[1]}' for o in options.items()])
        net.opt = net.opt + f' --RngRun={i}'
        net.e2e_global.stop_time = f'{global_stop}s'
        net.e2e_global.progress = f'100ms,{global_stop}s'

        # add probes for homa
        probe = e2e.E2ETracer('homa_traces', 'MsgBeginFinish')
        probe.file = f'{proto_fg}_{proto_bg}_trace_{nl}_{i}.tr'
        net.add_component(probe)

        net = tp.cast(sim.NS3E2ENet, net)
        for component in net.e2e_components:
            if component.id == '_agg0':
                probe = e2e.E2EPeriodicSampleProbe('send', 'NetDeviceSend')
                probe.file = f'net_device_send_simbricks_{proto_fg}_{proto_bg}.tr'
                component.components[0].add_component(probe)

        net.wait = True
        e.add_network(net)
        net.init_network()

    experiments.append(e)
