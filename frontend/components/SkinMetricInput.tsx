type SkinMetricInputProps = {
  label: string;
  value: number;
  onChange: (value: number) => void;
};

export default function SkinMetricInput({ label, value, onChange }: SkinMetricInputProps) {
  return (
    <div className="metric-input">
      <div className="metric-input-row">
        <label className="metric-input-label">{label}</label>
        <span className="metric-value">{value}/10</span>
      </div>

      <input
        className="range-input"
        type="range"
        min="0"
        max="10"
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
      />
    </div>
  );
}
