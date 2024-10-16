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
        m = {
            'cp_node': open('../images/homa/util/cp_node', 'rb'),
            'hosts': self.strfile(
                '127.0.0.1  localhost\n'
                '10.0.0.2   node1\n'
            )
        }
        return {**m, **super().config_files()}

    def run_cmds(self, node: nc.NodeConfig) -> tp.List[str]:
        cmd = [
            'cp /tmp/guest/hosts /etc/hosts',
            'cat /etc/hosts',
            'mkfifo input_pipe',
            'exec 3<> input_pipe',
            '/tmp/guest/cp_node < input_pipe &'
        ]
        if self.mode == 'client':
            cmd.append('sleep 1')
        cmd.append('date')
        if self.protocol == 'homa':
            cmd.append('cp /proc/net/homa_metrics /data/data/metrics1.txt')
        cmd.append('echo "log --file /data/data/node.log --level normal" > input_pipe')
        cmd.append(f'echo "log Start {self.mode}" > inpute_pipe')
        cmd.append(f'echo "{self.mode} --protocol {self.protocol} {self.options}" > input_pipe')
        if self.mode == 'client':
            cmd.append('sleep 8')
        else:
            cmd.append('sleep 10')
        cmd.append('date')
        if self.protocol == 'homa':
            cmd.append('cp /proc/net/homa_metrics /data/data/metrics2.txt')
        cmd.append('echo "stop clients" > inpute_pipe')
        cmd.append('echo "stop servers" > inpute_pipe')
        cmd.append('echo "exit" > input_pipe')
        cmd.append('sleep 1')
        cmd.append('cat /data/data/node.log')
        cmd.append('exec 3>&-')
        cmd.append('wait')
        cmd.append('sync')
        return cmd

experiments = []

# workload = ['w5', '100000', '1000000']
# host_types = ['gem5']
# protocol = ['tcp', 'homa']
params = [
    ('tcp', 'w5', '1'),
    ('tcp', 'w5', '30'),
    ('tcp', 'w4', '1'),
    ('tcp', 'w4', '5'),
    ('tcp', 'w4', '30'),
]
#for p, w, host_type in itertools.product(protocol, workload, host_types):
for p, w, cm in params:
    host_type = 'gem5'

    e = Experiment(f'{p}_{w}_{host_type}_cm{cm}')
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
    elif host_type == 'gem5kvm':

        def gem5_kvm(node_config: nc.NodeConfig):
            h = sims.Gem5Host(node_config)
            h.cpu_type = 'X86KvmCPU'
            return h
        
        HostClass = gem5_kvm
        sync = False
    else:
        raise NameError(host_type)

    # create client
    client_config = nc.HomaNode()
    client_config.ip = '10.0.0.1'
    client_config.memory = 2048
    client_config.do_extract_disk = True
    client_config.app = HomaApp()
    client_config.app.mode = 'client'
    client_config.app.protocol = p
    client_config.app.options = f'--workload {w} --gbps 2 --client-max {cm} '
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
    server_config.ip = '10.0.0.2'
    server_config.memory = 2048
    server_config.do_extract_disk = True
    server_config.app = HomaApp()
    server_config.app.mode = 'server'
    server_config.app.protocol = p
    server = HostClass(server_config)
    server.sync = sync
    server.name = 'server'
    server.wait = True
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
