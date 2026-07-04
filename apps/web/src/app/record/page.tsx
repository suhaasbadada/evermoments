"use client";

import { useRef, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Mic, Square, Check, ArrowLeft, Loader2 } from "lucide-react";
import { ingestMemoryEvent } from "@/lib/memoryClient";
import type { MemoryEvent, MemoryWarning } from "@/lib/memoryClient";
import { SafetyBanner } from "@/components/SafetyBanner";

type Step =
  | "idle"
  | "recording"
  | "transcribing"
  | "confirm"
  | "saving"
  | "done"
  | "error";

const PATIENT_ID = "p_001";

type SpeechRecognitionAlternativeLike = {
  transcript: string;
};

type SpeechRecognitionResultLike = {
  isFinal: boolean;
  0: SpeechRecognitionAlternativeLike;
};

type SpeechRecognitionEventLike = {
  resultIndex: number;
  results: ArrayLike<SpeechRecognitionResultLike>;
};

type SpeechRecognitionErrorEventLike = {
  error: string;
};

type SpeechRecognitionLike = {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  maxAlternatives: number;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null;
  onend: (() => void) | null;
  start: () => void;
  stop: () => void;
};

type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

type WindowWithSpeechRecognition = Window & {
  SpeechRecognition?: SpeechRecognitionConstructor;
  webkitSpeechRecognition?: SpeechRecognitionConstructor;
};

export default function RecordMemoryPage() {
  const router = useRouter();
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const speechRecognitionRef = useRef<SpeechRecognitionLike | null>(null);
  const transcriptRef = useRef("");
  const speechErrorRef = useRef<string | null>(null);

  const [step, setStep] = useState<Step>("idle");
  const [transcript, setTranscript] = useState("");
  const [pendingEvent, setPendingEvent] = useState<Partial<MemoryEvent> | null>(null);
  const [warning, setWarning] = useState<MemoryWarning | null>(null);
  const [errorMsg, setErrorMsg] = useState("");

  const stopSpeechRecognition = useCallback(async (): Promise<void> => {
    const recognition = speechRecognitionRef.current;
    if (!recognition) return;

    await new Promise<void>((resolve) => {
      let settled = false;

      const finish = () => {
        if (settled) return;
        settled = true;
        resolve();
      };

      const timeout = window.setTimeout(finish, 800);

      recognition.onend = () => {
        window.clearTimeout(timeout);
        finish();
      };

      try {
        recognition.stop();
      } catch {
        window.clearTimeout(timeout);
        finish();
      }
    });

    speechRecognitionRef.current = null;
  }, []);

  const startRecording = useCallback(async () => {
    // Guard: API not available (non-secure context, or old browser)
    if (!navigator.mediaDevices?.getUserMedia) {
      setErrorMsg(
        "Audio recording is not supported in this browser. Please use Chrome or Edge."
      );
      setStep("error");
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const speechWindow = window as WindowWithSpeechRecognition;
      const SpeechRecognitionCtor =
        speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition;

      if (!SpeechRecognitionCtor) {
        stream.getTracks().forEach((t) => t.stop());
        setErrorMsg(
          "Live speech transcription is not supported in this browser. Please use Chrome or Edge."
        );
        setStep("error");
        return;
      }

      transcriptRef.current = "";
      speechErrorRef.current = null;

      const recognition = new SpeechRecognitionCtor();
      recognition.continuous = true;
      recognition.interimResults = true;
      recognition.lang = "en-US";
      recognition.maxAlternatives = 1;

      recognition.onresult = (event) => {
        let finalChunk = "";

        for (let i = event.resultIndex; i < event.results.length; i += 1) {
          const result = event.results[i];
          if (result?.isFinal && result[0]?.transcript) {
            finalChunk += ` ${result[0].transcript}`;
          }
        }

        if (finalChunk.trim()) {
          transcriptRef.current = `${transcriptRef.current} ${finalChunk}`.trim();
        }
      };

      recognition.onerror = (event) => {
        const code = event.error;
        if (code === "not-allowed") {
          speechErrorRef.current =
            "Microphone access was blocked. Please allow microphone access and try again.";
          return;
        }
        if (code === "no-speech") {
          speechErrorRef.current =
            "I could not hear speech clearly. Please speak a bit louder and try again.";
          return;
        }
        speechErrorRef.current = `Speech recognition failed (${code}). Please try again.`;
      };

      speechRecognitionRef.current = recognition;

      const mr = new MediaRecorder(stream);

      mr.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        setStep("transcribing");

        try {
          await stopSpeechRecognition();

          if (speechErrorRef.current) {
            throw new Error(speechErrorRef.current);
          }

          const spokenTranscript = transcriptRef.current.trim();
          if (!spokenTranscript) {
            throw new Error(
              "No speech was captured. Please hold the phone closer and try again."
            );
          }

          const partial: Partial<MemoryEvent> = {
            transcript: spokenTranscript,
            event_type: "general",
          };

          setPendingEvent(partial);
          setTranscript(spokenTranscript);
          setStep("confirm");
        } catch (err) {
          console.error("Transcription error:", err);
          setErrorMsg(
            err instanceof Error
              ? err.message
              : "Could not process your recording. Please try again."
          );
          setStep("error");
        }
      };

      try {
        recognition.start();
        mr.start();
        mediaRecorderRef.current = mr;
        setStep("recording");
      } catch (err) {
        stream.getTracks().forEach((t) => t.stop());
        await stopSpeechRecognition();
        throw err;
      }
    } catch (err) {
      console.error("Mic error:", err);
      const name = err instanceof Error ? (err as DOMException).name : "";
      if (name === "NotAllowedError" || name === "PermissionDeniedError") {
        setErrorMsg(
          "Microphone access was blocked.\n\nTo fix: click the 🔒 lock icon in your browser address bar → set Microphone to Allow → refresh this page."
        );
      } else if (name === "NotFoundError") {
        setErrorMsg(
          "No microphone found. Please connect a microphone and try again."
        );
      } else {
        const detail = err instanceof Error ? err.message : String(err);
        setErrorMsg(`Microphone problem: ${detail}`);
      }
      setStep("error");
    }
  }, [stopSpeechRecognition]);

  const stopRecording = useCallback(() => {
    mediaRecorderRef.current?.stop();
  }, []);

  const saveMemory = useCallback(async () => {
    if (!pendingEvent) return;
    setStep("saving");
    try {
      const event: MemoryEvent = {
        patient_id: PATIENT_ID,
        recorded_at: new Date().toISOString(),
        event_type: pendingEvent.event_type ?? "general",
        transcript: pendingEvent.transcript ?? null,
        entities: pendingEvent.entities,
      };
      const result = await ingestMemoryEvent(event);
      setWarning(result.warning ?? null);
      setStep("done");
    } catch (err) {
      setErrorMsg(
        err instanceof Error ? err.message : "Could not save. Please try again."
      );
      setStep("error");
    }
  }, [pendingEvent]);

  const reset = useCallback(() => {
    setStep("idle");
    setTranscript("");
    setPendingEvent(null);
    setWarning(null);
    setErrorMsg("");
    transcriptRef.current = "";
    speechErrorRef.current = null;
  }, []);

  return (
    <main className="min-h-screen bg-amber-50 flex flex-col px-6 py-10 gap-6 max-w-xl mx-auto">
      <button
        type="button"
        onClick={() => router.back()}
        className="flex items-center gap-2 text-amber-800 text-lg self-start"
      >
        <ArrowLeft className="h-5 w-5" aria-hidden="true" />
        Back
      </button>

      <h1 className="text-4xl font-bold text-amber-900">Record a Memory</h1>

      {/* ── Idle ─────────────────────────────────────────────────────── */}
      {step === "idle" && (
        <div className="flex flex-col items-center gap-8 pt-6">
          <p className="text-2xl text-amber-700 text-center">
            Tap the button and speak
          </p>
          <button
            type="button"
            onClick={startRecording}
            className="h-44 w-44 rounded-full bg-rose-500 flex items-center justify-center shadow-2xl active:scale-95 transition-transform"
            aria-label="Start recording"
          >
            <Mic className="h-24 w-24 text-white" aria-hidden="true" />
          </button>
        </div>
      )}

      {/* ── Recording ────────────────────────────────────────────────── */}
      {step === "recording" && (
        <div className="flex flex-col items-center gap-8 pt-6">
          <p className="text-2xl text-rose-600 text-center animate-pulse font-medium">
            Listening... speak now
          </p>
          <button
            type="button"
            onClick={stopRecording}
            className="h-44 w-44 rounded-full bg-slate-800 flex items-center justify-center shadow-2xl active:scale-95 transition-transform"
            aria-label="Stop recording"
          >
            <Square className="h-24 w-24 text-white" aria-hidden="true" />
          </button>
          <p className="text-xl text-amber-600">Tap to stop</p>
        </div>
      )}

      {/* ── Transcribing ─────────────────────────────────────────────── */}
      {step === "transcribing" && (
        <div className="flex flex-col items-center gap-5 pt-12">
          <Loader2
            className="h-16 w-16 text-amber-600 animate-spin"
            aria-hidden="true"
          />
          <p className="text-2xl text-amber-700">Processing your words…</p>
        </div>
      )}

      {/* ── Confirm ──────────────────────────────────────────────────── */}
      {step === "confirm" && (
        <div className="flex flex-col gap-5">
          <div className="rounded-2xl bg-white border border-amber-200 shadow p-6">
            <p className="text-lg text-amber-600 mb-2">I heard:</p>
            <p className="text-2xl font-medium text-slate-900 leading-relaxed">
              {transcript}
            </p>
          </div>
          <button
            type="button"
            onClick={saveMemory}
            className="w-full rounded-2xl bg-green-600 px-6 py-6 text-2xl font-semibold text-white shadow-lg active:scale-95 transition-transform flex items-center justify-center gap-3"
          >
            <Check className="h-8 w-8" aria-hidden="true" />
            Save this memory
          </button>
          <button
            type="button"
            onClick={reset}
            className="w-full rounded-2xl bg-amber-100 px-6 py-5 text-xl font-medium text-amber-900 active:scale-95 transition-transform"
          >
            Try again
          </button>
        </div>
      )}

      {/* ── Saving ───────────────────────────────────────────────────── */}
      {step === "saving" && (
        <div className="flex flex-col items-center gap-5 pt-12">
          <Loader2
            className="h-16 w-16 text-green-600 animate-spin"
            aria-hidden="true"
          />
          <p className="text-2xl text-amber-700">Saving your memory…</p>
        </div>
      )}

      {/* ── Done ─────────────────────────────────────────────────────── */}
      {step === "done" && (
        <div className="flex flex-col gap-5">
          <div className="rounded-2xl bg-green-100 border border-green-300 p-6 text-center">
            <p className="text-5xl mb-3" aria-hidden="true">✅</p>
            <p className="text-2xl font-semibold text-green-900">Memory saved!</p>
            <p className="mt-2 text-lg text-green-700">
              Your memory is safely stored.
            </p>
          </div>

          {warning && <SafetyBanner warning={warning} />}

          <button
            type="button"
            onClick={reset}
            className="w-full rounded-2xl bg-rose-500 px-6 py-6 text-2xl font-semibold text-white shadow-lg active:scale-95 transition-transform flex items-center justify-center gap-3"
          >
            <Mic className="h-8 w-8" aria-hidden="true" />
            Record another
          </button>
          <button
            type="button"
            onClick={() => router.push("/")}
            className="w-full rounded-2xl bg-amber-100 px-6 py-5 text-xl font-medium text-amber-900 active:scale-95 transition-transform"
          >
            Go home
          </button>
        </div>
      )}

      {/* ── Error ────────────────────────────────────────────────────── */}
      {step === "error" && (
        <div className="flex flex-col gap-5">
          <div className="rounded-2xl bg-red-50 border border-red-300 p-6 text-center">
            <p className="text-5xl mb-3" aria-hidden="true">😕</p>
            <p className="text-2xl font-semibold text-red-900">
              Something went wrong
            </p>
            <p className="mt-2 text-lg text-red-700 whitespace-pre-line">{errorMsg}</p>
          </div>
          <button
            type="button"
            onClick={reset}
            className="w-full rounded-2xl bg-rose-500 px-6 py-6 text-2xl font-semibold text-white shadow-lg active:scale-95 transition-transform"
          >
            Try again
          </button>
        </div>
      )}
    </main>
  );
}
