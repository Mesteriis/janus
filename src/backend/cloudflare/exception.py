
class CloudflareError(Exception):
    pass

class CloudFlareTokenError(CloudflareError):
    pass


class DnsException(Exception):
    def __init__(self, fqdn: str, record_type: str, content: str):
        self.fqdn = fqdn
        self.record_type = record_type
        self.content = content
        super().__init__(f"DNS exception for {fqdn} ({record_type}): {content}")
