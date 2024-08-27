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

from simbricks.orchestration.experiments import Experiment
from simbricks.orchestration import nodeconfig as nc
from simbricks.orchestration import simulators as sims
import typing as tp
import itertools

class HomaApp(nc.AppConfig):

    def __init__(self) -> None:
        super().__init__()
        self.mode = ''
        self.protocol = ''
        self.options = ''

    # pylint: disable=consider-using-with
    def config_files(self) -> tp.Dict[str, tp.IO]:
        m = {'cp_node': open('../images/homa/util/cp_node', 'rb')}
        return {**m, **super().config_files()}

    def run_cmds(self, node: nc.NodeConfig) -> tp.List[str]:
        cmd = [
            'sleep 1',
            f'/tmp/guest/cp_node {self.mode} --protocol {self.protocol} {self.options} &',
            'sleep 10',
            'pkill cp_node',
        ]
        return cmd

experiments = []
workload = ['w5']
host_types = ['qemu', 'gem5', 'qt']
protocol = ['tcp', 'homa']
for p, w, host_type in itertools.product(protocol, workload, host_types):

    e = Experiment(f'single_{p}_{w}_{host_type}')
    e.checkpoint = False
    sync = True
    # host
    if host_type == 'qemu':
        HostClass = sims.QemuHost
        sync = False
    elif host_type == 'qt':

        def qemu_timing(node_config: nc.NodeConfig):
            h = sims.QemuHost(node_config)
            return h

        HostClass = qemu_timing
    elif host_type == 'gem5':
        HostClass = sims.Gem5Host
        e.checkpoint = True
    else:
        raise NameError(host_type)

    # create client
    client_config = nc.HomaNode()
    client_config.ip = '10.0.0.1'
    client_config.app = HomaApp()
    client_config.app.mode = 'client'
    client_config.app.protocol = p
    client_config.app.options = f'--workload {w}'
    client = HostClass(client_config)
    client.sync = sync
    client.name = 'client'
    client.wait = True  # wait for client simulator to finish execution
    e.add_host(client)

    # attach client's NIC
    client_nic = sims.I40eNIC()
    client_nic.sync_mode = 1 if sync else 0
    e.add_nic(client_nic)
    client.add_nic(client_nic)

    # create server
    server_config = nc.HomaNode()
    server_config.disk_image = 'homa'
    server_config.ip = '10.0.0.2'
    server_config.app = HomaApp()
    server_config.app.mode = 'server'
    server_config.app.protocol = p
    server = HostClass(server_config)
    server.sync = sync
    server.name = 'server'
    # server.wait = True
    e.add_host(server)

    # attach server's NIC
    server_nic = sims.I40eNIC()
    server_nic.sync_mode = 1 if sync else 0
    e.add_nic(server_nic)
    server.add_nic(server_nic)

    # connect NICs over network
    network = sims.SwitchNet()
    network.sync = sync
    e.add_network(network)
    client_nic.set_network(network)
    server_nic.set_network(network)


    experiments.append(e)
