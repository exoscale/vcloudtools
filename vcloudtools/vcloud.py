from collections import namedtuple

_Link = namedtuple('Link', 'type href rel name')
class Link(_Link):
    def __new__(cls, type, href, rel, name=None):
        return super(cls, Link).__new__(cls, type, href, rel, name)

_ResourceEntity = namedtuple('ResourceEntity', 'type href name')
class ResourceEntity(_ResourceEntity):
    def __new__(cls, type, href, name=None):
        return super(cls, ResourceEntity).__new__(cls, type, href, name)

_Org = namedtuple('Org', 'type href name id full_name description links')
class Org(_Org):
    def __new__(cls, type, href, name, id=None, full_name=None, description=None, links=None):
        return super(cls, Org).__new__(cls, type, href, name, id, full_name, description, links)

_OrgVdc = namedtuple('OrgVdc', 'type href name id storage compute links entities')
class OrgVdc(_OrgVdc):
    def __new__(cls, type, href, name, id=None, storage=None, compute=None, links=None, entities=None):
        return super(cls, OrgVdc).__new__(cls, type, href, name, id, storage, compute, links, entities)

_OrgList = namedtuple('OrgList', 'orgs')
class OrgList(_OrgList):

    def org_by_name(self, name):
        for o in self.orgs:
            if o.name == name:
                return o
        return None

_ExtNetList = namedtuple('ExtNetList', 'ext_nets')
class ExtNetList(_ExtNetList):

    def ext_net_by_name(self, name):
        for en in self.ext_nets:
            if en.name == name:
                return en
        return None

_ExtNet = namedtuple('ExtNet', 'type href name config id description links')
class ExtNet(_ExtNet):
    def __new__(cls, type, href, name, config=None, id=None, description=None, links=None):
        return super(cls, ExtNet).__new__(cls, type, href, name, config, id, description, links)

_OrgNet = namedtuple('OrgNet', 'name gateway netmask dns ranges')
class OrgNet(_OrgNet):
    def __new__(cls, name, gateway, netmask, dns, ranges):
        return super(cls, OrgNet).__new__(cls, name, gateway, netmask, dns, ranges)

_IpRange = namedtuple('IpRange', 'first last')
class IpRange(_IpRange):
    def __new__(cls, first, last):
        return super(cls, IpRange).__new__(cls, first, last)
