from collections import defaultdict
from datetime import datetime
from os import environ as env
import json
import logging

import lxml.etree
import requests

from vcloudtools.vcloud import *

log = logging.getLogger(__name__)


VCLOUD_AUTH_HEADER = 'x-vcloud-authorization'
VCLOUD_VERSION = '1.5'
VCLOUD_MIME = 'application/*+xml;version=%s' % VCLOUD_VERSION
VCLOUD_NS = {
    'vcloud': 'http://www.vmware.com/vcloud/v%s' % VCLOUD_VERSION
}

OVF_NS = { 'ovf': 'htp://schemas.dmtf.org/ovf' }


class ClientError(Exception):
    pass


class APIError(Exception):
    pass


class VCloudAPIClient(object):
    def __init__(self, root=None):
        """
        Create a new instance of the vCloud API client, optionally specifying the API root URL
        """

        #self._session = requests.Session(headers={'accept': VCLOUD_MIME})
        self._session = requests.Session()
        self._session.headers={'accept': VCLOUD_MIME}
        self.token = envget('auth_token')

        if root is not None:
            self.root = root
        elif envget('api_root') is not None:
            self.root = envget('api_root')
        else:
            msg = "No known API root for vCloud. Perhaps you need to set ${0}?".format(envkey('api_root'))
            raise ClientError(msg)

        self._links = None

        if self.logged_in:
            self._links = self._fetch_initial_links()

        self.VCLOUD_NS = VCLOUD_NS
        self.OVF_NS = OVF_NS

        log.debug("Created %s", self)

    def _req(self, method, url, _raise=True, *args, **kwargs):
        """
        Make and error check a request in the current session
        """
        res = self._session.request(method, url, *args, **kwargs)
        if _raise:
            _custom_raise_for_status(res)
        return res

    def _url(self, path):
        """
        Return an absolute URL for the specified path
        """
        return self.root + path

    def _lookup(self, typ):
        """
        Look up a URL for a resource of the specified type
        """
        full_typ = 'application/vnd.vmware.{0}+xml'.format(typ)

        if full_typ in self._links:
            return self._links[full_typ][0].href
        else:
            raise APIError("Don't know anything about type '{0}'".format(typ))

    def _fetch_initial_links(self):
        """
        Fetch the "root" resource URLs for this session
        """
        res = self._req('get', self._url('/session'))

        etree = lxml.etree.fromstring(res.content)
        links = _parse_links(etree)

        return links

    def login(self, username, password):
        """
        Retrieve an auth token from the vCloud API using a username and password
        """
        res = self._req(
            'post',
            self._url('/sessions'),
            auth=(username, password),
        )

        self.token = res.headers[VCLOUD_AUTH_HEADER]
        # At __init__ self.logged_in is not set and thus never populates the list
        self._links = self._fetch_initial_links()

    def browse(self, path='/'):
        """
        Make an arbitrary request to the vCloud API at the specified path
        """
        res = self._req('get', self._url(path))
        return res

    def ext_net_list(self):
        """
        Retrieve a list of all external networks
        """
        res = self._req('get', self._lookup('admin.vcloud'))

        etree = lxml.etree.fromstring(res.content)
        return _parse_ext_net_list(etree)

    def org_list(self):
        """
        Retrieve the OrgList
        """
        res = self._req('get', self._lookup('vcloud.orgList'))

        etree = lxml.etree.fromstring(res.content)
        return _parse_org_list(etree)

    def org(self, name):
        """
        Retrieve an org by name
        """
        org_short = self.org_list().org_by_name(name)

        res = self._req('get', org_short.href)

        etree = lxml.etree.fromstring(res.content)
        return _parse_org(etree)

    def org_nets(self, org):
        """
        Retrieve the networks for a given organization
        """
        nets = []
        for l in org.links['application/vnd.vmware.vcloud.orgNetwork+xml']:
            res = self._req('get', l.href)
            etree = lxml.etree.fromstring(res.content)

            nets.append(_parse_org_nets(etree))

        return nets

    def org_vdcs(self, org):
        """
        Retrieve a list of organization virtualDataCenters
        """
        vdcs = []
        for l in org.links['application/vnd.vmware.vcloud.vdc+xml']:
            res = self._req('get', l.href)
            etree = lxml.etree.fromstring(res.content)
            vdcs.append(_parse_org_vdcs(etree))

        return vdcs

    def org_vapps(self, org):
        """
        Retrieve a list of vapps for a given organization
        """
        ovdcs = self.org_vdcs(org)
        r_entities = []
        for ovdc in ovdcs:
            r_entities += ovdc.entities['application/vnd.vmware.vcloud.vApp+xml']
        return r_entities


    def ext_net(self, name):
        """
        Retrieve an external network by name
        """
        ext_net_short = self.ext_net_list().ext_net_by_name(name)

        res = self._req('get', ext_net_short.href)

        etree = lxml.etree.fromstring(res.content)
        return _parse_ext_net(etree)

    def ip_ranges(self, el):
        config = el.find('vcloud:Configuration', VCLOUD_NS)
        scope = config.find('vcloud:IpScope', VCLOUD_NS)
        iprange = scope.find('vcloud:IpRanges', VCLOUD_NS)
        ranges = [r for r in iprange.findall('vcloud:IpRange', VCLOUD_NS)]
        return ranges

    @property
    def token(self):
        return self._token

    @token.setter
    def token(self, tok):
        self._token = tok
        self._session.headers[VCLOUD_AUTH_HEADER] = self._token

    @property
    def logged_in(self):
        """
        Return a boolean representing logged-in status
        """
        res = self._req('get', self._url('/session'), _raise=False)
        return res.ok

    def __str__(self):
        return '<VCloudAPIClient {0}>'.format(self.root)



def envkey(key):
    return 'VCLOUD_{0}'.format(key.upper())


def envget(key, default=None):
    return env.get(
        envkey(key),
        default
    )

def _parse_org_vdcs(el):
    type_ = el.attrib['type']
    href  = el.attrib['href']
    name  = el.attrib['name']
    id_   = el.attrib['id']

    raw_storage_capacity = el.find('vcloud:StorageCapacity', VCLOUD_NS)
    s_cap = {}
    for k in raw_storage_capacity:
        s_cap[k.tag.split('}')[1]] = k.text

    raw_compute_capacity = el.find('vcloud:ComputeCapacity', VCLOUD_NS)
    c_cap = {'cpu':{}, 'memory':{}}
    raw_cpu = raw_compute_capacity.find('vcloud:Cpu', VCLOUD_NS)
    for k in raw_cpu:
        c_cap['cpu'][k.tag.split('}')[1]] = k.text
    raw_memory = raw_compute_capacity.find('vcloud:Memory', VCLOUD_NS)
    for k in raw_memory:
        c_cap['memory'][k.tag.split('}')[1]] = k.text

    links = _parse_links(el)
    r_entities = _parse_resource_entities(el)

    # TODO: AvailableNetworks, Capabilities, Quotas, etc

    return OrgVdc(
        type=type_,
        href=href,
        name=name,
        id=id_,
        storage=s_cap,
        compute=c_cap,
        links=links,
        entities=r_entities
    )


def _parse_org_nets(el):
    configuration = el.find('vcloud:Configuration', VCLOUD_NS)
    ipscope = configuration.find('vcloud:IpScope', VCLOUD_NS)
    
    gateway = ipscope.find('vcloud:Gateway', VCLOUD_NS).text
    netmask = ipscope.find('vcloud:Netmask', VCLOUD_NS).text
    dns = ipscope.find('vcloud:DnsSuffix', VCLOUD_NS).text
    ranges = _parse_ip_ranges(el.attrib['name'], ipscope.find('vcloud:IpRanges', VCLOUD_NS))

    return OrgNet(
        el.attrib['name'],
        gateway,
        netmask,
        dns,
        ranges
    )

def _parse_ip_ranges(net_name, el):
    raw_ranges = el.findall('vcloud:IpRange', VCLOUD_NS)

    ranges = []
    for r in raw_ranges:
        first = r.find('vcloud:StartAddress', VCLOUD_NS).text
        last = r.find('vcloud:EndAddress', VCLOUD_NS).text
        name = net_name+" - ("+first+"-"+last+")"
        ranges.append(IpRange(first,last))
    return ranges

def _parse_links(el):
    res = defaultdict(list)
    for c in el.findall('vcloud:Link', VCLOUD_NS):
        link = _parse_link(c)
        res[link.type].append(link)
    return res

def _parse_resource_entities(el):
    el = el.find('vcloud:ResourceEntities', VCLOUD_NS)
    res = defaultdict(list)
    for c in el.findall('vcloud:ResourceEntity', VCLOUD_NS):
        re = _parse_resource_entity(c)
        res[re.type].append(re)
    return res

def _parse_link(el):
    return Link(**el.attrib)

def _parse_resource_entity(el):
    return ResourceEntity(**el.attrib)

def _parse_ext_net_list(el):
    ext_nets = [_parse_ext_net_short(c) for c in el.find('vcloud:Networks', VCLOUD_NS).findall('vcloud:Network', VCLOUD_NS)]
    return ExtNetList(ext_nets=ext_nets)

def _parse_org_list(el):
    orgs = [_parse_org_short(c) for c in el.findall('vcloud:Org', VCLOUD_NS)]
    return OrgList(orgs=orgs)

def _parse_ext_net_short(el):
    return ExtNet(**el.attrib)

def _parse_org_short(el):
    return Org(**el.attrib)

def _parse_ext_net(el):
    type_ = el.attrib['type']
    href  = el.attrib['href']
    name  = el.attrib['name']
    id_   = el.attrib['id']

    description = el.find('vcloud:Description', VCLOUD_NS).text
    config = el.find('vcloud:Configuration', VCLOUD_NS)

    links = _parse_links(el)

    return ExtNet(
        type=type_,
        href=href,
        name=name,
        config=config,
        id=id_,
        description=description,
        links=links
    )

def _parse_org(el):
    type_ = el.attrib['type']
    href  = el.attrib['href']
    name  = el.attrib['name']
    id_   = el.attrib['id']

    full_name = el.find('vcloud:FullName', VCLOUD_NS).text
    description = el.find('vcloud:Description', VCLOUD_NS).text

    links = _parse_links(el)

    return Org(
        type=type_,
        href=href,
        name=name,
        id=id_,
        full_name=full_name,
        description=description,
        links=links
    )


def _custom_raise_for_status(res):
    try:
        res.raise_for_status()
    except requests.RequestException as err:
        raise APIError(err)

