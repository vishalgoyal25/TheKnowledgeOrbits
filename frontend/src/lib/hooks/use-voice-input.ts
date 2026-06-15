"use client";

/**
 * frontend/src/lib/hooks/use-voice-input.ts
 * ────────────────────────────────────────────
 * Web Speech API wrapper — ChatGPT-style hold-to-record behaviour.
 *
 * Flow:
 *   startListening()  → mic opens, stays open until user clicks stop (continuous=true)
 *   user speaks       → isFinal chunks accumulate in accumulatedRef; interim shows live
 *   stopListening()   → .stop() called → browser flushes last chunk → onend fires
 *   onend             → transcript state set to full accumulated text → isListening=false
 *   VoiceInput.tsx    → detects isListening false transition → fires onTranscript(transcript)
 *
 * Why continuous=true?
 *   With continuous=false the browser auto-fires onend on any natural pause,
 *   discarding everything the user said. continuous=true keeps the session alive
 *   until we explicitly call .stop().
 *
 * 2-minute hard cap: auto-stops at 120 s so the session never hangs indefinitely.
 *
 * Cross-device support:
 *   ✅ Chrome desktop / Android Chrome  — full support
 *   ✅ Edge desktop                     — full support
 *   ✅ Safari desktop 14+               — webkitSpeechRecognition
 *   ✅ Safari iOS 14.1+                 — webkitSpeechRecognition (continuous=true works)
 *   ❌ Firefox                          — isSupported=false → mic button hidden
 */

import { useCallback, useEffect, useRef, useState } from "react";

// ── Browser type shim ─────────────────────────────────────────────────────────

interface SpeechRecognitionResult {
  readonly isFinal: boolean;
  readonly 0: { readonly transcript: string };
}
interface SpeechRecognitionResultList {
  readonly length: number;
  item(index: number): SpeechRecognitionResult;
  [index: number]: SpeechRecognitionResult;
}
interface SpeechRecognitionEvent extends Event {
  readonly resultIndex: number;
  readonly results: SpeechRecognitionResultList;
}
interface SpeechRecognitionErrorEvent extends Event {
  readonly error: string;
}
interface SpeechRecognitionInstance extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  onstart: (() => void) | null;
  onresult: ((e: SpeechRecognitionEvent) => void) | null;
  onerror: ((e: SpeechRecognitionErrorEvent) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}

function getSpeechRecognitionCtor():
  | (new () => SpeechRecognitionInstance)
  | null {
  if (typeof window === "undefined") return null;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const w = window as any;
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

// ── Public API ────────────────────────────────────────────────────────────────

export interface VoiceInputState {
  isSupported: boolean;
  isListening: boolean;
  transcript: string; // live: accumulated + current interim; final: full committed text
  error: string | null;
}
export interface VoiceInputActions {
  startListening: () => void;
  stopListening: () => void;
  clearTranscript: () => void;
}

// ── Hook ──────────────────────────────────────────────────────────────────────

const AUTO_STOP_MS = 120_000; // 2-minute cap

export function useVoiceInput(): VoiceInputState & VoiceInputActions {
  const [isSupported, setIsSupported] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [error, setError] = useState<string | null>(null);

  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null);
  const accumulatedRef = useRef(""); // all isFinal pieces joined together
  const autoStopTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // SSR-safe: detect support client-side only.
  useEffect(() => {
    setIsSupported(getSpeechRecognitionCtor() !== null);
  }, []);

  function clearAutoStop() {
    if (autoStopTimerRef.current !== null) {
      clearTimeout(autoStopTimerRef.current);
      autoStopTimerRef.current = null;
    }
  }

  const startListening = useCallback(() => {
    const Ctor = getSpeechRecognitionCtor();
    if (!Ctor) return;

    // Fresh session — wipe previous state.
    setError(null);
    setTranscript("");
    accumulatedRef.current = "";

    const recognition = new Ctor();
    recognitionRef.current = recognition;

    recognition.continuous = true; // stay alive across natural pauses (no auto-onend)
    recognition.interimResults = true; // live preview while the user is mid-word
    recognition.lang = "en-IN"; // Indian English accent + UPSC terminology

    recognition.onstart = () => {
      setIsListening(true);
      // Hard 2-minute cap — stops recognition automatically if user forgets.
      autoStopTimerRef.current = setTimeout(() => {
        recognitionRef.current?.stop();
      }, AUTO_STOP_MS);
    };

    recognition.onresult = (e: SpeechRecognitionEvent) => {
      let interimText = "";
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const result = e.results[i];
        if (result.isFinal) {
          // Commit confirmed text — this persists across pauses.
          accumulatedRef.current += result[0].transcript + " ";
        } else {
          interimText += result[0].transcript;
        }
      }
      // Live display: everything confirmed + what's being said right now.
      setTranscript(accumulatedRef.current + interimText);
    };

    recognition.onerror = (e: SpeechRecognitionErrorEvent) => {
      clearAutoStop();
      const messages: Record<string, string> = {
        "not-allowed":
          "Microphone access denied. Please allow microphone permission and try again.",
        "no-speech": "No speech detected. Please speak clearly and try again.",
        network:
          "Network error during voice recognition. Please check your connection.",
        aborted: "", // user stopped manually — not an error
      };
      const msg =
        messages[e.error] ?? "Voice input unavailable. Please type instead.";
      if (msg) setError(msg);
      setIsListening(false);
    };

    recognition.onend = () => {
      clearAutoStop();
      // Lock in the final accumulated text (browser has finished flushing all isFinal chunks).
      const final = accumulatedRef.current.trim();
      setTranscript(final);
      setIsListening(false);
    };

    try {
      recognition.start();
    } catch {
      setError("Voice input already active. Please wait.");
      setIsListening(false);
    }
  }, []);

  const stopListening = useCallback(() => {
    clearAutoStop();
    recognitionRef.current?.stop();
    // isListening → false is set inside onend (after browser flushes remaining audio).
  }, []);

  const clearTranscript = useCallback(() => {
    setTranscript("");
    setError(null);
    accumulatedRef.current = "";
  }, []);

  // Abort on unmount to silence browser warnings.
  useEffect(() => {
    return () => {
      clearAutoStop();
      recognitionRef.current?.abort();
    };
  }, []);

  return {
    isSupported,
    isListening,
    transcript,
    error,
    startListening,
    stopListening,
    clearTranscript,
  };
}
