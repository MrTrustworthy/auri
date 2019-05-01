from typing import Generator, Tuple, Union

import socket
import select
import re
Socket = socket.socket


class DeviceFinder:
    def __init__(self):
        self.device_id = "nanoleaf_aurora:light"
        self.ssdp_ip = "239.255.255.250"
        self.device_port = 1900
        self.bind_port = 9090
        self.ssdp_mx = 3

    def find_aurora_addresses(self, search_for_amount: int = 10) -> Generator[Tuple[str, str], None, None]:
        """Returns a list of the (IP, MAC addresses of all Auroras found on the network"""

        aurora_ips = []
        aurora_socket = self._prepare_socket()
        while len(aurora_ips) < search_for_amount:
            response = DeviceFinder._get_socket_response(aurora_socket)
            aurora_ip = self._get_aurora_ip_from_response(response)
            if aurora_ip is None or aurora_ip in aurora_ips:
                continue
            aurora_ips.append(aurora_ip)
            yield aurora_ip, self._get_device_mac_from_response(response)

        return

    def _get_aurora_ip_from_response(self, response: str) -> Union[str, None]:
        if response is None:
            return
        location = re.search(r"Location: http://([\d\\.]*):16021", response).group(1)
        return location

    def _get_device_mac_from_response(self, response: str) -> str:
        mac = re.search("nl-deviceid: ([\w\d:]*)", response).group(1)
        return mac

    @staticmethod
    def _get_socket_response(sock: Socket) -> Union[str, None]:
        try:
            ready = select.select([sock], [], [], 5)
            if ready[0]:
                response = sock.recv(1024).decode("utf-8")
                return response
        except socket.error:
            sock.close()
            raise

    def _prepare_socket(self) -> Socket:

        request = ['M-SEARCH * HTTP/1.1',
                   f'HOST: {self.ssdp_ip}:{self.device_port}',
                   'MAN: "ssdp:discover"',
                   f'ST: {self.device_id}',
                   f'MX: {self.ssdp_mx}']
        request = '\r\n'.join(request).encode('utf-8')
        aurora_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        aurora_socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, self.ssdp_mx)
        aurora_socket.bind((socket.gethostname(), self.bind_port))
        aurora_socket.sendto(request, (self.ssdp_ip, self.device_port))
        aurora_socket.setblocking(False)
        return aurora_socket
