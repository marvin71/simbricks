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

# Allow own class to be used as type for a method's argument
from __future__ import annotations

from abc import ABC, abstractmethod
import ipaddress
import random
import typing as tp

import simbricks.orchestration.e2e_components as e2e


class E2ETopology(ABC):

    @abstractmethod
    def add_to_network(self, net):
        pass

    @abstractmethod
    def get_switches(self):
        pass

    @abstractmethod
    def get_links(self):
        pass


class E2EDumbbellTopology(E2ETopology):

    def __init__(self):
        self.left_switch = e2e.E2ESwitchNode("_leftSwitch")
        self.right_switch = e2e.E2ESwitchNode("_rightSwitch")
        self.link = e2e.E2ESimpleChannel("_link")
        self.link.left_node = self.left_switch
        self.link.right_node = self.right_switch

    def add_to_network(self, net):
        net.add_component(self.left_switch)
        net.add_component(self.right_switch)
        net.add_component(self.link)

    def add_left_component(self, component: e2e.E2EComponent):
        self.left_switch.add_component(component)

    def add_right_component(self, component: e2e.E2EComponent):
        self.right_switch.add_component(component)

    @property
    def mtu(self):
        return self.left_switch.mtu

    @mtu.setter
    def mtu(self, mtu: str):
        self.left_switch.mtu = mtu
        self.right_switch.mtu = mtu

    @property
    def data_rate(self):
        return self.link.data_rate

    @data_rate.setter
    def data_rate(self, data_rate: str):
        self.link.data_rate = data_rate

    @property
    def queue_size(self):
        return self.link.queue_size

    @queue_size.setter
    def queue_size(self, queue_size: str):
        self.link.queue_size = queue_size

    @property
    def delay(self):
        return self.link.delay

    @delay.setter
    def delay(self, delay: str):
        self.link.delay = delay

    def get_switches(self):
        return [self.left_switch, self.right_switch]

    def get_links(self):
        return [self.link]


class DCFatTree(E2ETopology):

    def __init__(self, basename='', **kwargs):
        self.params = {
            'n_spine_sw': 1,
            'n_agg_bl': 5,
            'n_agg_sw': 1,
            'n_agg_racks': 6,
            'h_per_rack': 40,
            'mtu': '1448',
            'queue_type': 'ns3::PTPQueue',
            'spine_link_delay': '1us',
            'spine_link_rate': '100Gbps',
            'spine_link_queue': '512KB',
            'agg_link_delay': '1us',
            'agg_link_rate': '100Gbps',
            'agg_link_queue': '512KB',
            'sbhost_eth_latency': '500ns',
            'sbhost_sync_delay': '100ns',
        }
        for (n,v) in kwargs.items():
            self.params[n] = v

        self.basename = basename

        self.switches = []
        self.spine_switches = []
        self.agg_blocks = []

        self.links = []
        self.spine_agg_links = []
        self.agg_tor_links = []

        self.hosts = []

        self.n_simbricks_host = 0

        bn = basename

        # Create spine switches
        for i in range(0, self.params['n_spine_sw']):
            sw = e2e.E2ESwitchNode(f"_{bn}spine{i}")
            sw.weight = (self.params['n_agg_bl'] * self.params['n_agg_sw'] *
                self.params['n_agg_racks'] * self.params['h_per_rack'])
            sw.mtu = self.params['mtu']
            self.spine_switches.append(sw)
            self.switches.append(sw)

        # Create aggregation blocks
        for i in range(0, self.params['n_agg_bl']):
            ab = {
                'id': f'agg{i}',
                'switches': [],
                'racks': []
            }

            # Create switches in aggregation blocks
            for j in range(0, self.params['n_agg_sw']):
                sw = e2e.E2ESwitchNode(f"_{bn}agg{i}_{j}")
                sw.weight = (self.params['n_agg_racks'] *
                    self.params['h_per_rack'])
                sw.mtu = self.params['mtu']
                ab['switches'].append(sw)
                self.switches.append(sw)

            # Create racks (including ToRs)
            for j in range(0, self.params['n_agg_racks']):
                tor = e2e.E2ESwitchNode(f"_{bn}tor{i}_{j}")
                tor.weight = self.params['h_per_rack']
                sw.mtu = self.params['mtu']
                r = {
                    'id': f'rack{i}_{j}',
                    'tor': tor,
                    'hosts': []
                }
                ab['racks'].append(r)
                self.switches.append(tor)
            self.agg_blocks.append(ab)

        # wire up switches
        for (i,ab) in enumerate(self.agg_blocks):
            for (j,agg_sw) in enumerate(ab['switches']):
                agg_sw = ab['switches'][j]
                # Wire up aggregation switch to spine switches
                for (si,spine_sw) in enumerate(self.spine_switches):
                    l = e2e.E2ESimpleChannel(f"_{bn}link_sp_ab{i}_as{j}_s{si}")
                    l.left_node = agg_sw
                    l.right_node = spine_sw
                    l.delay = self.params['spine_link_delay']
                    l.data_rate = self.params['spine_link_rate']
                    l.queue_type = self.params['queue_type']
                    l.queue_size = self.params['spine_link_queue']
                    self.links.append(l)
                    self.spine_agg_links.append(l)

                # Wire up ToRs to aggregation switches
                for (ti,r) in enumerate(ab['racks']):
                    l = e2e.E2ESimpleChannel(
                            f"_{bn}link_ab{i}_as{j}_tor{ti}")
                    l.left_node = r['tor']
                    l.right_node = agg_sw
                    l.delay = self.params['agg_link_delay']
                    l.data_rate = self.params['agg_link_rate']
                    l.queue_type = self.params['queue_type']
                    l.queue_size = self.params['agg_link_queue']
                    self.links.append(l)
                    self.agg_tor_links.append(l)

    def add_to_network(self, net):
        for sw in self.switches:
            net.add_component(sw)
        for l in self.links:
            net.add_component(l)
        #for h in self.hosts:
        #    net.add_component(h)

    def capacity(self):
        max_hs = (self.params['n_agg_bl'] * self.params['n_agg_racks'] *
            self.params['h_per_rack'])
        return max_hs - len(self.hosts)

    def racks_with_capacity(self):
        racks = []
        for (i,ab) in enumerate(self.agg_blocks):
            for (j,r) in enumerate(ab['racks']):
                cap = self.params['h_per_rack'] - len(r['hosts'])
                if cap <= 0:
                    continue
                racks.append((i, j, cap))
        return racks

    def add_host(self, agg, rack, h):
        r = self.agg_blocks[agg]['racks'][rack]
        if len(r['hosts']) >= self.params['h_per_rack']:
            raise BufferError('Requested rack is full')
        r['hosts'].append(h)
        self.hosts.append(h)
        r['tor'].add_component(h)

    def add_host_r(self, h):
        rs = self.racks_with_capacity()
        if not rs:
            raise BufferError('Network is full')
        (agg, rack, _) = random.choice(rs)
        self.add_host(agg, rack, h)
        return (agg, rack)

    def wrap_simbricks_host(self, nic):
        i = self.n_simbricks_host
        self.n_simbricks_host += 1

        host = e2e.E2ESimbricksHost(f'_sbh-{i}-{nic.name}')
        host.eth_latency = self.params['sbhost_eth_latency']
        host.sync_delay = self.params['sbhost_sync_delay']
        host.simbricks_component = nic
        return host

    def add_simbricks_host(self, agg, rack, nic):
        self.add_host(agg, rack, self.wrap_simbricks_host(nic))

    def add_simbricks_host_r(self, nic):
        return self.add_host_r(self.wrap_simbricks_host(nic))

    def get_switches(self):
        return self.switches

    def get_links(self):
        return self.links


def add_contig_bg(topo, subnet='10.42.0.0/16', **kwargs):
    params = {
        'link_rate': '5Gbps',
        'link_delay': '1us',
        'link_queue_size': '512KB',
        'link_queue_type': 'ns3::PTPQueue',
        'congestion_control': e2e.CongestionControl.CUBIC,
        'app_stop_time': '60s',
    }
    for (k,v) in kwargs.items():
        params[k] = v

    pairs = int(topo.capacity() / 2)
    ipn = ipaddress.ip_network(subnet)
    prefix = f'/{ipn.prefixlen}'
    ips = ipn.hosts()
    for i in range(0, pairs):
        s_ip = str(next(ips))
        c_ip = str(next(ips))

        s_host = e2e.E2ESimpleNs3Host(f'bg_s-{i}')
        s_host.delay = params['link_delay']
        s_host.data_rate = params['link_rate']
        s_host.ip = s_ip + prefix
        s_host.queue_size = params['link_queue_size']
        s_host.queue_type = params['link_queue_type']
        s_host.congestion_control = params['congestion_control']
        s_app = e2e.E2EPacketSinkApplication('sink')
        s_app.local_ip = '0.0.0.0:5000'
        s_app.stop_time = params['app_stop_time']
        s_host.add_component(s_app)
        s_probe = e2e.E2EPeriodicSampleProbe('probe', 'Rx')
        s_probe.interval = '100ms'
        s_probe.file = f'sink-rx-{i}'
        s_app.add_component(s_probe)
        topo.add_host_r(s_host)

        c_host = e2e.E2ESimpleNs3Host(f'bg_c-{i}')
        c_host.delay = params['link_delay']
        c_host.data_rate = params['link_rate']
        c_host.ip = c_ip + prefix
        c_host.queue_size = params['link_queue_size']
        c_host.queue_type = params['link_queue_type']
        c_host.congestion_control = params['congestion_control']
        c_app = e2e.E2EBulkSendApplication('sender')
        c_app.remote_ip = s_ip + ':5000'
        c_app.stop_time = params['app_stop_time']
        c_host.add_component(c_app)
        topo.add_host_r(c_host)


def add_homa_bg(topo, subnet='10.2.0.0/16', **kwargs):
    params = {
        'link_rate': '20Gbps',
        'link_delay': '500ns',
        'link_queue_size': '512KB',
        'link_queue_type': 'ns3::HomaPFifoQueue',
        'app_stop_time': '60s',
    }
    for (k,v) in kwargs.items():
        params[k] = v


    n = topo.capacity()
    ipn = ipaddress.ip_network(subnet)
    prefix = f'/{ipn.prefixlen}'
    ip_pool = ipn.hosts()
    ips = [str(next(ip_pool)) for i in range(0,n)]
    remotes = [f'{ip}:3000' for ip in ips]

    for i in range(0, n):
        ip = ips[i]

        s_host = e2e.E2ESimpleNs3Host(f'bg_h-{i}')
        s_host.delay = params['link_delay']
        s_host.data_rate = params['link_rate']
        s_host.ip = ip + prefix
        s_host.queue_size = params['link_queue_size']
        s_host.queue_type = params['link_queue_type']

        remotes_to_connect = random.choices(remotes, k=10)
        # print(remotes_to_connect)

        if (params['app_proto'] == 'tcp'):
            s_app = e2e.E2EMsgGenApplicationTCP('msggen')
            s_app.stop_time = params['app_stop_time']
            s_app.remotes = remotes_to_connect
            # s_app.max_msg = 1
            s_host.add_component(s_app)
            s_probe = e2e.E2EPeriodicSampleProbe('probe', 'Rx')
            s_probe.interval = '500ms'
            exp_name = params['exp_name']
            s_probe.file = f'{exp_name}_sink-rx-{i}'
            s_app.add_component(s_probe)
        elif(params['app_proto'] == 'homa'):
            s_app = e2e.E2EMsgGenApplication('msggen')
            s_app.stop_time = params['app_stop_time']
            s_app.remotes = remotes_to_connect
            # s_app.max_msg = 1
            s_host.add_component(s_app)
            s_probe = e2e.E2EPeriodicSampleProbe('probe', 'Rx')
            s_probe.interval = '500ms'
            exp_name = params['exp_name']
            s_probe.file = f'{exp_name}_sink-rx-{i}'
            s_app.add_component(s_probe)

        topo.add_host_r(s_host)


class HomaTopology(E2ETopology):

    def __init__(self, basename='', **kwargs):
        self.params = {
            'n_agg_sw': 1,
            'n_agg_racks': 9,
            'h_per_rack': 16,
            'n_remotes': 4,
            'mtu': '1500',
            'agg_link_delay': '250ns',
            'agg_link_rate': '160Gbps',
            'agg_link_queue_type': 'ns3::HomaPFifoQueue',
            'agg_link_queue_size': '500000p',
            'tor_link_delay': '250ns',
            'tor_link_rate': '10Gbps',
            'tor_link_queue_type': 'ns3::DropTailQueue<Packet>',
            'tor_link_queue_size': '500000p',
            'host_link_queue_type': 'ns3::HomaPFifoQueue',
            'host_link_queue_size': '500000p',
            'pfifo_num_bands': '8',
            'network_load': '0.8',
            'start_time': '3s',
            'stop_time': '23s',
            'msg_size_dist_file': '',
        }
        for (n, v) in kwargs.items():
            self.params[n] = v

        self.basename = basename

        self.switches: tp.List[e2e.E2ESwitchNode] = []
        self.agg_switches: tp.List[e2e.E2ESwitchNode] = []
        self.tor_switches: tp.List[e2e.E2ESwitchNode] = []

        self.links = []
        self.agg_tor_links = []

        self.hosts = []

        bn = basename

        # create aggregation switches
        for i in range(self.params['n_agg_sw']):
            sw = e2e.E2ESwitchNode(f'_{bn}agg{i}')
            sw.mtu = self.params['mtu']
            self.agg_switches.append(sw)
            self.switches.append(sw)

        # create tor switches
        for i in range(self.params['n_agg_racks']):
            sw = e2e.E2ESwitchNode(f'_{bn}tor{i}')
            sw.mtu = self.params['mtu']
            self.tor_switches.append(sw)
            self.switches.append(sw)

        # connect tor switches to aggregation switches
        for (i, agg_sw) in enumerate(self.agg_switches):
            for (j, tor_sw) in enumerate(self.tor_switches):
                l = e2e.E2ESimpleChannel(f'_{bn}link_agg{i}_tor{j}')
                l.left_node = tor_sw
                l.right_node = agg_sw
                l.delay = self.params['agg_link_delay']
                l.data_rate = self.params['agg_link_rate']
                l.queue_type = self.params['agg_link_queue_type']
                l.queue_size = self.params['agg_link_queue_size']
                l.mtu = self.params['mtu']
                self.links.append(l)
                self.agg_tor_links.append(l)

    def add_to_network(self, net):
        for switch in self.switches:
            net.add_component(switch)
        for link in self.links:
            net.add_component(link)

    def get_links(self):
        return self.links

    def get_switches(self):
        return self.switches

    def add_homa_hosts(self, subnet='10.2.0.0/16'):
        ipn = ipaddress.ip_network(subnet)
        prefix = f'/{ipn.prefixlen}'
        ips = ipn.hosts()

        for (i, tor_sw) in enumerate(self.tor_switches):
            for j in range(self.params['h_per_rack']):
                host = e2e.E2ESimpleNs3Host(f'_{self.basename}tor{i}_host{j}')
                host.delay = self.params['tor_link_delay']
                host.data_rate = self.params['tor_link_rate']
                host.ip = str(next(ips)) + prefix
                host.mapping.update({
                    'InnerQueueType': self.params['host_link_queue_type'],
                    'InnerQueue-MaxSize': self.params['host_link_queue_size'],
                    'InnerQueue-NumBands': self.params['pfifo_num_bands'],
                    'OuterQueueType': self.params['tor_link_queue_type'],
                    'OuterQueue-MaxSize': self.params['tor_link_queue_size']
                })
                host.queue_type = ''
                host.mtu = self.params['mtu']
                self.hosts.append(host)
                tor_sw.add_component(host)

    def add_homa_app(
        self,
        AppClass: tp.Type[tp.Union[e2e.E2EMsgGenApplication,
                                   e2e.E2EMsgGenApplicationTCP]
                         ] = e2e.E2EMsgGenApplication,
        selected_hosts: tp.List[int] = [],
        n_remotes = None
    ):
        if n_remotes is None:
            n_remotes = self.params['n_remotes']
        addresses = []
        if selected_hosts == []:
            hosts = self.hosts
        else:
            hosts = []
            for host in selected_hosts:
                hosts.append(self.hosts[host])
        for (i, host) in enumerate(hosts):
            addresses.append(host.ip.split('/')[0] + f':{2000+i}')
        for (i, host) in enumerate(hosts):
            app = AppClass(f'_{self.basename}host{i}_homa_app')
            app.ip = addresses[i].split(':')[0]
            app.port = addresses[i].split(':')[1]
            app.load = self.params['network_load']
            app.start_time = self.params['start_time']
            app.stop_time = self.params['stop_time']
            
            # randomly draw the remotes to send data to
            N = n_remotes
            addresses_wo_self = addresses.copy()
            addresses_wo_self.pop(i)
            assert len(addresses_wo_self) >= N
            remotes = random.sample(addresses_wo_self, N)
            # add ping app for all remote addresses
            for (j, address) in enumerate(remotes):
                ping_app = e2e.E2EApplication(f'_{self.basename}host{i}_ping_app_{j}')
                ping_app.type = 'Generic'
                start_time = 0.1 + 0.001 * j
                ping_app.start_time = f'{start_time}s'
                ping_app.stop_time = f'{0.1 + N * 0.001 + 2}s'
                ping_app.mapping.update({
                    'TypeId': 'ns3::Ping',
                    'Destination(Ipv4Address)': address.split(':')[0],
                    'Size': '16',
                    'Count': '1',
                    'Timeout': '1s',
                    'VerboseMode': 'Silent',
                })
                host.add_component(ping_app)
            app.remotes = remotes

            app.payload_size = str(int(self.params['mtu']) - 20 - 20)
            app.msg_size_dist_file = self.params['msg_size_dist_file']
            host.add_component(app)

    def print_ip_addresses(self, selected_hosts: tp.List[int]):
        addresses = []
        for host in selected_hosts:
            addresses.append(self.hosts[host].ip.split('/')[0])
        print(addresses)
