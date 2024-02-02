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

import simbricks.orchestration.experiments as exp
import simbricks.orchestration.nodeconfig as node
import simbricks.orchestration.simulators as sim
import simbricks.orchestration.e2e_components as e2e
from simbricks.orchestration.simulator_utils import create_tcp_cong_hosts
from simbricks.orchestration.e2e_topologies import E2EDumbbellTopology


mtu = 1500
congestion_control = e2e.CongestionControl.CUBIC

link_rate = 200 # in Mbps
link_latency = 5 # in ms
bdp = int(link_rate * link_latency / 1000 * 10**6) # Bandwidth-delay product
cpu_freq = '5GHz'
cpu_freq_qemu = '2GHz'
sys_clock = '1GHz'  # if not set, default 1GHz

ip_start = '192.168.64.1'

experiments = []

queue_size = bdp

options = {
    'ns3::TcpSocket::SegmentSize': f'{mtu-52}',
    'ns3::TcpSocket::SndBufSize': '524288',
    'ns3::TcpSocket::RcvBufSize': '524288',
}

net = sim.NS3E2ENet()
net.opt = ' '.join([f'--{o[0]}={o[1]}' for o in options.items()])
net.use_dce = True

topology = E2EDumbbellTopology()
topology.data_rate = f'{link_rate}Mbps'
topology.delay = f'{link_latency}ms'
topology.queue_size = f'{queue_size}B'
topology.mtu = f'{mtu-52}'
net.add_component(topology)

host = e2e.E2ESimpleNs3Host('ns3-dce-client')
host.delay = '100us'
host.data_rate = f'{link_rate}Mbps'
host.ip = '192.168.64.1/24'
host.queue_size = f'{queue_size}B'
host.congestion_control = congestion_control
app = e2e.E2EDceApplication('iperf-client')
app.stop_time = '20s'
app.binary = 'iperf'
app.arguments = '-c 192.168.64.2 -i 1'
host.add_component(app)
topology.add_left_component(host)

e = exp.Experiment(
    'gt-ib-dumbbell-' + str(congestion_control) + 'TCPm' + f'-{mtu}'
)
e.add_network(net)

freq = cpu_freq

# simbricks host
def gem5_timing(node_config: node.NodeConfig):
    h = sim.Gem5Host(node_config)
    #h.sys_clock = sys_clock
    return h

HostClass = gem5_timing
e.checkpoint = True

NicClass = sim.I40eNIC
NcClass = node.I40eTCPCongNode

servers = create_tcp_cong_hosts(
    e,
    1,
    'server',
    net,
    NicClass,
    HostClass,
    NcClass,
    node.TcpCongServer,
    freq,
    mtu,
    congestion_control.gem5,
    ip_start=2
)

for i, server in enumerate(servers, 1):
    host = e2e.E2ESimbricksHost(f'simbricksserver-{i}')
    host.eth_latency = '1us'
    host.simbricks_host = server.nics[0]
    topology.add_right_component(host)

net.init_network()
net.wait = True

print(e.name)
experiments.append(e)
