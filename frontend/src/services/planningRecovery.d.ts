export interface RecoveryAction { id: string; label: string; target?: string; value?: string | number; places?: string[] }
export function planningRecovery(pending?: { code?: string; message?: string; provider?: string; diagnostics?: { places?: string[]; required?: string[] } }, chinese?: boolean, current?: { budget?: number; hotelTier?: string }): { reason: string; actions: RecoveryAction[] }
