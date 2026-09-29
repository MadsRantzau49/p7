import { useState } from "react";
import "../css/timeRangeSlider.css";

type TimeRangeSliderProps = {
  startTime: string;
  endTime: string;
  onChange: (startTime: string, endTime: string) => void;
};

function timeToMinutes(time: string): number {
  const [hours, minutes] = time.split(":").map(Number);

  return hours * 60 + minutes;
}

function minutesToTime(totalMinutes: number): string {
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;

  return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(
    2,
    "0"
  )}`;
}

export default function TimeRangeSlider({
  startTime,
  endTime,
  onChange,
}: TimeRangeSliderProps) {
  const min = 0;
  const max = 23 * 60 + 59;

  const [activeThumb, setActiveThumb] = useState<
    "start" | "end" | null
  >(null);

  const startMinutes = timeToMinutes(startTime);
  const endMinutes = timeToMinutes(endTime);

  const startPercentage = (startMinutes / max) * 100;
  const endPercentage = (endMinutes / max) * 100;

  const middle =
    (startPercentage + endPercentage) / 2;

  let startZIndex = middle <= 50 ? 4 : 5;
  let endZIndex = middle <= 50 ? 5 : 4;

  if (activeThumb === "start") {
    startZIndex = 10;
  }

  if (activeThumb === "end") {
    endZIndex = 10;
  }

  function changeStart(value: number) {
    const newStart = Math.min(
      value,
      endMinutes
    );

    onChange(
      minutesToTime(newStart),
      endTime
    );
  }

  function changeEnd(value: number) {
    const newEnd = Math.max(
      value,
      startMinutes
    );

    onChange(
      startTime,
      minutesToTime(newEnd)
    );
  }

  return (
    <div className="time-slider">
      <div className="time-slider-value-row">
        <div className="time-slider-time-field">
          <label htmlFor="start-time">
            Start
          </label>

          <input
            id="start-time"
            type="time"
            step={60}
            value={startTime}
            max={endTime}
            onChange={(event) => {
              const value =
                event.target.value;

              if (value) {
                changeStart(
                  timeToMinutes(value)
                );
              }
            }}
          />
        </div>

        <div className="time-slider-time-field">
          <label htmlFor="end-time">
            End
          </label>

          <input
            id="end-time"
            type="time"
            step={60}
            value={endTime}
            min={startTime}
            onChange={(event) => {
              const value =
                event.target.value;

              if (value) {
                changeEnd(
                  timeToMinutes(value)
                );
              }
            }}
          />
        </div>
      </div>

      {/* Slider */}
      <div className="time-slider-track-wrapper">
        <div className="time-slider-track" />

        <div className="time-slider-ticks">
          {Array.from({
            length: 13,
          }).map((_, index) => (
            <span
              key={index}
              className="time-slider-tick"
              style={{
                left: `${
                  (index / 12) * 100
                }%`,
              }}
            />
          ))}
        </div>

        <div
          className="time-slider-selected"
          style={{
            left: `${startPercentage}%`,
            width: `${
              endPercentage -
              startPercentage
            }%`,
          }}
        />

        <input
          type="range"
          min={min}
          max={max}
          step={1}
          value={startMinutes}
          className="time-slider-range-input"
          style={{
            zIndex: startZIndex,
          }}
          onPointerDown={() =>
            setActiveThumb("start")
          }
          onPointerUp={() =>
            setActiveThumb(null)
          }
          onFocus={() =>
            setActiveThumb("start")
          }
          onBlur={() =>
            setActiveThumb(null)
          }
          onChange={(event) =>
            changeStart(
              Number(
                event.target.value
              )
            )
          }
          aria-label="Start time"
        />

        <input
          type="range"
          min={min}
          max={max}
          step={1}
          value={endMinutes}
          className="time-slider-range-input"
          style={{
            zIndex: endZIndex,
          }}
          onPointerDown={() =>
            setActiveThumb("end")
          }
          onPointerUp={() =>
            setActiveThumb(null)
          }
          onFocus={() =>
            setActiveThumb("end")
          }
          onBlur={() =>
            setActiveThumb(null)
          }
          onChange={(event) =>
            changeEnd(
              Number(
                event.target.value
              )
            )
          }
          aria-label="End time"
        />
      </div>

      <div className="time-slider-labels">
        <span>00:00</span>
        <span>06:00</span>
        <span>12:00</span>
        <span>18:00</span>
        <span>23:59</span>
      </div>
    </div>
  );
}