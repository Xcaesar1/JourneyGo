export interface RecoveryAction { id: string; label: string; target?: string; value?: string | number }
export function planningRecovery(pending?: { code?: string; message?: string; provider?: string }, chinese?: boolean, current?: { budget?: number; hotelTier?: string }): { reason: string; actions: RecoveryAction[] }
