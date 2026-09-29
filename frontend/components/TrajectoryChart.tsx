interface TrajectoryChartProps {
  timesDays: number[];
  p10: number[];
  p50: number[];
  p90: number[];
  baseline: number;
  label: string;
}

const WIDTH = 640;
const HEIGHT = 280;
const LEFT = 44;
const RIGHT = 16;
const TOP = 16;
const BOTTOM = 40;
const MAX_SCORE = 10;
const BAND_LABEL = "middle 80% of simulated outcomes";

export default function TrajectoryChart({ timesDays, p10, p50, p90, baseline, label }: TrajectoryChartProps) {
  const plotWidth = WIDTH - LEFT - RIGHT;
  const plotHeight = HEIGHT - TOP - BOTTOM;
  const lastDay = timesDays[timesDays.length - 1];
  const x = (day: number) => Number((LEFT + (day / lastDay) * plotWidth).toFixed(1));
  const y = (score: number) => Number((TOP + (1 - score / MAX_SCORE) * plotHeight).toFixed(1));
  const point = (day: number, score: number) => `${x(day).toFixed(1)},${y(score).toFixed(1)}`;
  const bandPoints = [...timesDays.map((day, index) => point(day, p90[index])), ...timesDays.map((day, index) => point(day, p10[index])).reverse()].join(" ");
  const medianPoints = timesDays.map((day, index) => point(day, p50[index])).join(" ");
  const yTicks = Array.from({ length: MAX_SCORE / 2 + 1 }, (_, index) => index * 2);
  const xTicks = timesDays.filter((day) => day % 28 === 0 || day === lastDay);
  const durationWeeks = lastDay / 7;

  return (
    <figure className="trajectory-figure">
      <svg className="trajectory-svg" viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label={`${label}: simulated range of outcomes over ${durationWeeks} weeks`}>
        {yTicks.map((score) => (
          <line className="trajectory-grid" key={score} x1={x(0)} x2={x(lastDay)} y1={y(score)} y2={y(score)} />
        ))}
        <polygon className="trajectory-band" points={bandPoints} />
        <line className="trajectory-start" x1={x(timesDays[0])} x2={x(lastDay)} y1={y(baseline)} y2={y(baseline)} />
        <polyline className="trajectory-median" points={medianPoints} />
        <line className="trajectory-axis" x1={x(0)} x2={x(lastDay)} y1={y(0)} y2={y(0)} />
        {yTicks.map((score) => <text className="trajectory-tick-label" key={score} x={x(0) - 8} y={y(score)} textAnchor="end" dominantBaseline="middle">{score}</text>)}
        {xTicks.map((day) => (
          <g key={day}>
            <line className="trajectory-tick" x1={x(day)} x2={x(day)} y1={y(0)} y2={y(0) + 5} />
            <text className="trajectory-tick-label" x={x(day)} y={y(0) + 22} textAnchor={day === timesDays[0] ? "start" : day === lastDay ? "end" : "middle"}>Week {day / 7}</text>
          </g>
        ))}
        <rect className="trajectory-band" x={x(lastDay) - 236} y={y(10) + 7} width="14" height="10" />
        <text className="trajectory-band-label" x={x(lastDay) - 6} y={y(10) + 16} textAnchor="end">{BAND_LABEL}</text>
      </svg>
      <figcaption className="trajectory-caption meta">The solid line shows the median simulated outcome; the dashed line shows the starting score.</figcaption>
    </figure>
  );
}
