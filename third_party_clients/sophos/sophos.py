import ipaddress
import logging
import urllib.parse
import xml.etree.ElementTree as ET

import requests
from common import _get_password
from third_party_clients.sophos.sophos_config import (
    BLOCK_LIST_NAME,
    HOSTNAME,
    IS_ENCRYPTED,
    PORT,
)
from third_party_clients.third_party_interface import (
    ThirdPartyInterface,
    VectraAccount,
    VectraDetection,
    VectraHost,
    VectraStaticIP,
)
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)


class Client(ThirdPartyInterface):
    def __init__(self, **kwargs):
        self.name = "Sophos Client"
        self.module = "sophos"
        self.init_log(kwargs)
        self.baseurl = f"https://{HOSTNAME}:{PORT}/webconsole/APIController?reqxml="
        self.login_xml = f"<Login><Username>{_get_password("Sophos", "Username", modify=kwargs["modify"])}</Username><Password passwordform=\"{'encrypted' if IS_ENCRYPTED else 'plain'}\">{_get_password("Sophos", "Password", modify=kwargs["modify"])}</Password></Login>"
        self._login_check()
        # Instantiate parent class
        ThirdPartyInterface.__init__(self)

    def init_log(self, kwargs):
        dict_config = kwargs.get("dict_config", {})
        dict_config["loggers"].update({self.name: dict_config["loggers"]["VAR"]})
        logging.config.dictConfig(dict_config)
        self.logger = logging.getLogger(self.name)

    def block_host(self, host: VectraHost) -> list[str]:
        return self._block_ip(ip=host.ip)

    def unblock_host(self, host: VectraHost) -> list[str]:
        return self._unblock_ip(ip=host.ip)

    def groom_host(self, host: VectraHost) -> dict:
        self.logger.warning("Sophos client does not implement host grooming")
        return []

    def block_account(self, account: VectraAccount) -> list:
        # this client only implements Host-based blocking
        self.logger.warning("Sophos client does not implement account-based blocking")
        return []

    def unblock_account(self, account: VectraAccount) -> list:
        # this client only implements Host-based blocking
        self.logger.warning("Sophos client does not implement account-based blocking")
        return []

    def block_detection(self, detection: VectraDetection):
        # this client only implements Host-based blocking
        self.logger.warning("Sophos client does not implement detection-based blocking")
        return []
    
    def unblock_detection(self, detection: VectraDetection):
        # this client only implements Host-based blocking
        return []

    def block_static_dst_ips(self, ips: VectraStaticIP) -> list:
        # this client only implements Host-based blocking
        self.logger.warning("Sophos client does not implement static IP-based blocking")
        return []

    def unblock_static_dst_ips(self, ips: VectraStaticIP) -> list:
        # this client only implements Host-based blocking
        self.logger.warning("Sophos client does not implement static IP-based blocking")
        return []

    def _make_api_call(self, request_xml: str) -> requests.Response:
        full_reqxml = f"<Request>{self.login_xml}{request_xml}</Request>"
        self.logger.debug(f"Making request: {self.baseurl + full_reqxml}")
        reqxml_encoded = urllib.parse.quote_plus(full_reqxml)
        url = self.baseurl + reqxml_encoded
        response = requests.get(url=url, verify=False)
        response.raise_for_status()
        return response

    def _login_check(self):
        r = self._make_api_call("")
        xml = ET.fromstring(r.text)
        if xml.find("Login").find("status").text == "Authentication Successful":
            self.logger.info("Sophos Firewall Integration API Login Check Successful")
        else:
            self.logger.error(
                "Sophos Firewall Integration API Login Check Failed. Please check credentials."
            )
            exit()

    def _get_blocked_ips(self) -> list[str]:
        r = self._make_api_call(
            f'<Get><IPHost><Filter><key name="Name" criteria="=">{BLOCK_LIST_NAME}</key></Filter></IPHost></Get>'
        )
        xml = ET.fromstring(r.text)
        iphosts = xml.findall("IPHost")
        if len(iphosts) > 1:
            self.logger.warning(
                f'Multiple IPHosts with Name equaling "{BLOCK_LIST_NAME}" found. Using first one. Please verify firewall is setup according to documentation.'
            )
        elif len(iphosts) == 0:
            self.logger.error(
                f'No IPHost with Name equaling "{BLOCK_LIST_NAME}" found. Please verify firewall is setup according to documentation.'
            )
            exit()
        blocked_ips = iphosts[0].find("ListOfIPAddresses").text.split(sep=",")
        self.logger.debug(f"Retrieved currently blocked ips: {blocked_ips}")
        return blocked_ips

    def _update_blocked_ips(self, ips_to_block: list[str]) -> bool:
        ip_csv = ",".join(ips_to_block)
        r = self._make_api_call(
            f'<Set operation="update"><IPHost><Name>{BLOCK_LIST_NAME}</Name><IPFamily>IPv4</IPFamily><HostType>IPList</HostType><ListOfIPAddresses>{ip_csv}</ListOfIPAddresses></IPHost></Set>'
        )
        xml = ET.fromstring(r.text)
        status = xml.find("IPHost").find("Status")
        status_code = status.attrib["code"]
        status_msg = status.text
        if status_code != "200":
            self.logger.error(
                f'Error updating IP list of IPHost "{BLOCK_LIST_NAME}". (Status Code: {status_code} - Message: {status_msg})'
            )
            return False
        return True

    def _block_ip(self, ip: str) -> list[str]:
        if self._validate_ip_address(ip):
            blocked_ips = self._get_blocked_ips()
            if ip not in blocked_ips:
                blocked_ips.append(ip)
                if self._update_blocked_ips(blocked_ips):
                    return [ip]
        return []

    def _unblock_ip(self, ip: str) -> list[str]:
        if self._validate_ip_address(ip):
            blocked_IPs = self._get_blocked_ips()
            if ip in blocked_IPs:
                blocked_IPs.remove(ip)
                if self._update_blocked_ips(blocked_IPs):
                    return [ip]
        return []

    def _validate_ip_address(self, ip: str):
        try:
            _ = ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False
