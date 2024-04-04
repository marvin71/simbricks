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
import simbricks.orchestration.experiments as exp
import simbricks.orchestration.nodeconfig as node
import simbricks.orchestration.simulators as sim
import simbricks.orchestration.e2e_components as e2e
from simbricks.orchestration.simulator_utils import create_tcp_cong_hosts
from simbricks.orchestration.e2e_topologies import (HomaTopology, add_homa_bg)

random.seed(42)

types_of_protocol = ['tcp', 'homa']

initial_credit = '7'
total_prio_bands = '8'
unsched_prio_bands = '2'
inbnd_rtx_timeout = '1ms'
outbound_rtx_timeout = '10ms'
network_load = '0.8'
start_time = '3s'
stop_time = '23s'
msg_size_dist_file = ''

options = {
    'ns3::TcpSocket::SegmentSize': '1448',
    'ns3::TcpSocket::SndBufSize': '524288',
    'ns3::TcpSocket::RcvBufSize': '524288',
    'ns3::Ipv4GlobalRouting::RandomEcmpRouting': '1',
    'ns3::Ipv4L3Protocol::MayFragment': 'false',
    'ns3::HomaL4Protocol::RttPackets': initial_credit,
    'ns3::HomaL4Protocol::NumTotalPrioBands': total_prio_bands,
    'ns3::HomaL4Protocol::NumUnschedPrioBands': unsched_prio_bands,
    'ns3::HomaL4Protocol::InbndRtxTimeout': inbnd_rtx_timeout,
    'ns3::HomaL4Protocol::OutbndRtxTimeout': outbound_rtx_timeout,
}

experiments = []

for p in types_of_protocol:
    e = exp.Experiment('homa_' + '_ns3_' + p)

    if p == 'homa':
        AppClass = e2e.E2EMsgGenApplication
    elif p == 'tcp':
        AppClass = e2e.E2EMsgGenApplicationTCP
    else:
        raise NameError(f'Unkown {p} in types_of_protocol')

    topology = HomaTopology(
        pfifo_num_bands=total_prio_bands,
        network_load=network_load,
        start_time=start_time,
        stop_time=stop_time,
        msg_size_dist_file=msg_size_dist_file,
    )

    net = sim.NS3E2ENet()
    net.opt = ' '.join([f'--{o[0]}={o[1]}' for o in options.items()])
    #net.e2e_global.stop_time = '60s'
    net.e2e_global.progress = '100ms,23s'
    net.add_component(topology)

    net.wait = True
    e.add_network(net)

    topology.add_homa_hosts()
    topology.add_homa_app(AppClass)
    net.init_network()

    experiments.append(e)
