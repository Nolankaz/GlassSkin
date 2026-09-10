type SkinMetricBarProps = {
  label: string;
  value: number;
};

export default function SkinMetricBar({ label, value }: SkinMetricBarProps) {
  return (
    <div className="metric-bar">
      <div className="metric-bar-header">
        <span>{label}</span>
        <span className="metric-value">{value}/10</span>
      </div>

      <div className="metric-track">
        <div className="metric-fill" style={{ width: `${value * 10}%` }} />
      </div>
    </div>
  );
}
