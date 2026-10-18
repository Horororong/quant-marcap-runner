"""Classify an explicit OpenDART XML service error, never a financial fact.

800 is system maintenance: stop this batch, preserve existing attempts and
defer the receipt. No in-process retry or historic quarantine reset.
Malformed/HTML responses are not silently classified as maintenance.
"""
import xml.etree.ElementTree as ET

def service_status(content):
    try:
        root = ET.fromstring(content)
    except (ET.ParseError, TypeError, ValueError):
        return None
    if root.tag != 'result':
        return None
    status = root.findtext('status')
    return status.strip() if status is not None else None

def defer_maintenance(content, control, paused_error):
    if service_status(content) != '800':
        return
    if control is not None:
        control.stop('SERVICE_MAINTENANCE_800')
    raise paused_error('DART status=800; service maintenance; receipt deferred')

def defer_http_transient(status, control, paused_error):
    """A bounded transport/service outage is never a permanent document defect."""
    if status not in {408, 500, 502, 503, 504}:
        return
    reason = 'TRANSIENT_HTTP_' + str(status)
    if control is not None:
        control.stop(reason)
    raise paused_error(reason + '; receipt deferred')
