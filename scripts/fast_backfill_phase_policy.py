"""Start another API phase only after a naturally completed legacy phase.

A local deadline/request/signal stop is NOT spare budget. This policy never
changes schedules, quotas, persisted task states or parser certification.
"""

def modern_phase_decision(limit,legacy):
 if limit<=0:return False,'DISABLED_BY_BATCH_LIMIT'
 if legacy.get('legacy_rate_limited'):return False,'LEGACY_RATE_LIMIT'
 reason=legacy.get('legacy_stop_reason')
 if reason!='BATCH_COMPLETE':return False,'LEGACY_STOP_'+str(reason or 'UNKNOWN')
 return True,'LEGACY_BATCH_COMPLETE'
