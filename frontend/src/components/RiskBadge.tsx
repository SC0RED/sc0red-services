import { getRiskTierLabel } from '@/lib/utils/riskUtils'

export default function RiskBadge({ tier }: { tier: string }) {
    return (
        <span className={`badge badge-${tier}`}>
            <span
                style={{
                    width: '6px',
                    height: '6px',
                    borderRadius: '50%',
                    background: 'currentColor',
                    display: 'inline-block',
                }}
            />
            {getRiskTierLabel(tier)}
        </span>
    )
}
