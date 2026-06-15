"use client";

import { useEffect, useRef } from "react";
import { Mic, MicOff } from "lucide-react";
import { useVoiceInput } from "@/lib/hooks/use-voice-input";

export interface VoiceInputProps {
  onTranscript: (text: string) => void;
  disabled?: boolean;
}

export default function VoiceInput({
  onTranscript,
  disabled = false,
}: VoiceInputProps) {
  const {
    isSupported,
    isListening,
    transcript,
    error,
    startListening,
    stopListening,
  } = useVoiceInput();

  // Fire onTranscript when the recording session ends (isListening: true → false).
  // We use a ref to detect the direction of the transition rather than calling
  // onTranscript() synchronously in handleClick — at that point the hook's onend
  // callback hasn't fired yet, so `transcript` state still reflects interim text.
  // By the time isListening changes to false, onend has committed the full
  // accumulated text to `transcript`.
  const prevListeningRef = useRef(false);
  useEffect(() => {
    if (prevListeningRef.current && !isListening && transcript.trim()) {
      onTranscript(transcript.trim());
    }
    prevListeningRef.current = isListening;
  }, [isListening]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!isSupported) return null;

  function handleClick() {
    if (disabled) return;
    if (isListening) {
      stopListening(); // onend will fire → isListening goes false → useEffect above fires
    } else {
      startListening();
    }
  }

  return (
    <div className="flex flex-col items-center gap-1">
      <button
        type="button"
        onClick={handleClick}
        disabled={disabled}
        aria-label={isListening ? "Stop recording" : "Start voice input"}
        className={[
          "relative flex items-center justify-center w-9 h-9 rounded-full transition-all duration-200",
          "focus:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-2",
          isListening
            ? "bg-red-500 text-white shadow-md shadow-red-200"
            : "bg-gray-100 text-gray-500 hover:bg-gray-200 hover:text-gray-700",
          disabled ? "opacity-40 cursor-not-allowed" : "cursor-pointer",
        ].join(" ")}
      >
        {/* Pulse ring while recording */}
        {isListening && (
          <span className="absolute inset-0 rounded-full animate-ping bg-red-400 opacity-30 pointer-events-none" />
        )}

        {isListening ? (
          <MicOff className="w-4 h-4 relative z-10" />
        ) : (
          <Mic className="w-4 h-4" />
        )}
      </button>

      {/* Live transcript preview — shows accumulated + current interim while recording */}
      {isListening && transcript && (
        <p className="text-[10px] text-gray-500 italic max-w-[140px] text-center leading-snug line-clamp-3">
          {transcript}
        </p>
      )}

      {/* Error message */}
      {error && !isListening && (
        <p className="text-[10px] text-red-500 max-w-[140px] text-center leading-tight">
          {error}
        </p>
      )}
    </div>
  );
}
