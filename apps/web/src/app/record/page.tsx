"use client";

import { useRef, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { Mic, Square, Check, ArrowLeft, Loader2 } from "lucide-react";
import { mockTranscribeAndExtract } from "@/lib/mockVoiceBackend";
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

export default function RecordMemoryPage() {
  const router = useRouter();
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const [step, setStep] = useState<Step>("idle");
  const [transcript, setTranscript] = useState("");
  const [pendingEvent, setPendingEvent] = useState<Partial<MemoryEvent> | null>(null);
  const [warning, setWarning] = useState<MemoryWarning | null>(null);
  const [errorMsg, setErrorMsg] = useState("");

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
      const mr = new MediaRecorder(stream);
      chunksRef.current = [];

      mr.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      mr.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        setStep("transcribing");
        try {
          const partial = await mockTranscribeAndExtract(blob);
          setPendingEvent(partial);
          setTranscript(partial.transcript ?? "");
          setStep("confirm");
        } catch (err) {
          console.error("Transcription error:", err);
          setErrorMsg("Could not process your recording. Please try again.");
          setStep("error");
        }
      };

      mr.start();
      mediaRecorderRef.current = mr;
      setStep("recording");
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
  }, []);

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
