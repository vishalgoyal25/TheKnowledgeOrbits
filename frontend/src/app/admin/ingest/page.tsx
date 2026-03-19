"use client";

import React, { useState, useEffect } from "react";

type SubjectNode = {
  id: string;
  name: string;
};

type ProgramNode = {
  id: string;
  name: string;
  subjects: SubjectNode[];
};

export default function AdminIngestPage() {
  const [hierarchy, setHierarchy] = useState<ProgramNode[]>([]);

  // Selection State
  const [selectedProgram, setSelectedProgram] = useState<string>("");
  const [selectedSubject, setSelectedSubject] = useState<string>("");

  // Accuracy Overrides
  const [chapterName, setChapterName] = useState("");
  const [startingPageOffset, setStartingPageOffset] = useState("1");

  // Metadata State
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [sourceType, setSourceType] = useState("ncert");
  const [edition, setEdition] = useState("");
  const [sourceVersion, setSourceVersion] = useState("");
  const [isbn, setIsbn] = useState("");
  const [year, setYear] = useState("");

  // UI State
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<{
    text: string;
    type: "success" | "error" | "info";
  } | null>(null);

  // Fetch Hierarchy
  useEffect(() => {
    async function loadHierarchy() {
      try {
        const res = await fetch(
          "http://localhost:8000/api/v1/knowledge/hierarchy/",
        );
        if (!res.ok) throw new Error("Failed to fetch knowledge hierarchy");
        const data = await res.json();
        setHierarchy(data);
        if (data.length > 0) {
          setSelectedProgram(data[0].id); // Auto-select UPSC CSE
        }
      } catch (err: unknown) {
        console.error("Hierarchy Load Error", err);
      }
    }
    loadHierarchy();
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      const selected = e.target.files[0];
      setFile(selected);
      if (!title) {
        setTitle(selected.name.replace(/\.[^/.]+$/, "")); // Default title to filename
      }
    }
  };

  const currentProgram = hierarchy.find((p) => p.id === selectedProgram);
  const handleIngest = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file || !selectedSubject || !title) {
      setMessage({
        text: "Please fill all required fields and select a file.",
        type: "error",
      });
      return;
    }

    // Fallback if the user somehow removed it from .env
    const adminKey = process.env.NEXT_PUBLIC_INTERNAL_ADMIN_KEY || "";
    if (!adminKey) {
      setMessage({
        text: "Internal Admin Key missing from .env.local",
        type: "error",
      });
      return;
    }

    setLoading(true);
    setMessage({
      text: "Uploading and processing massive document... (This can take minutes)",
      type: "info",
    });

    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("title", title);
      formData.append("source_type", sourceType);
      formData.append("program_id", selectedProgram);
      formData.append("subject_id", selectedSubject);

      if (chapterName) formData.append("chapter_name", chapterName);
      if (startingPageOffset)
        formData.append("starting_page_offset", startingPageOffset);

      if (edition) formData.append("source_edition", edition);
      if (sourceVersion) formData.append("source_version", sourceVersion);
      if (isbn) formData.append("isbn", isbn);
      if (year) formData.append("publication_year", year);

      const res = await fetch(
        "http://localhost:8000/api/v1/content/admin-ingest/",
        {
          method: "POST",
          headers: {
            "X-Admin-Key": adminKey,
          },
          body: formData,
        },
      );

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || data.detail || "Ingestion Failed");
      }

      setMessage({
        text: `Success! Formatted ${data.chunks_created} chunks mapped to the Knowledge Engine.`,
        type: "success",
      });
      setFile(null);
    } catch (err: unknown) {
      const e = err as Error;
      setMessage({ text: `Error: ${e.message}`, type: "error" });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-200 py-12 px-6">
      <div className="max-w-4xl mx-auto space-y-8">
        <h1 className="text-3xl font-bold text-white tracking-tight border-b border-slate-800 pb-4">
          Direct Supabase Content Ingestion 🚀
        </h1>
        <p className="text-slate-400">
          Strictly inject NCERTs and Standard Books into chunks, mapping them
          1:1 with the UPSC Root Knowledge Hierarchy.
        </p>

        {message && (
          <div
            className={`p-4 rounded-lg font-medium border ${
              message.type === "error"
                ? "bg-red-950/30 border-red-900 text-red-400"
                : message.type === "success"
                  ? "bg-emerald-950/30 border-emerald-900 text-emerald-400"
                  : "bg-blue-950/30 border-blue-900 text-blue-400"
            }`}
          >
            {message.type === "info" && (
              <span className="animate-pulse mr-2">⚙️</span>
            )}
            {message.text}
          </div>
        )}

        <form
          onSubmit={handleIngest}
          className="bg-slate-900 border border-slate-800 rounded-2xl p-8 space-y-8 shadow-2xl"
        >
          {/* Hierarchy Selection */}
          <div className="space-y-4">
            <h2 className="text-xl font-semibold text-white">
              1. Semantic Knowledge Mapping
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">
                  Program
                </label>
                <select
                  disabled
                  value={selectedProgram}
                  className="w-full bg-slate-800/50 border border-slate-700 rounded-lg px-4 py-3 text-slate-300"
                >
                  {hierarchy.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">
                  Subject (Required)
                </label>
                <select
                  required
                  value={selectedSubject}
                  onChange={(e) => setSelectedSubject(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-3 text-white"
                >
                  <option value="">-- Dropdown Loaded Automatically -- </option>
                  {currentProgram?.subjects.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">
                  Chapter Name Override (Optional)
                </label>
                <input
                  type="text"
                  value={chapterName}
                  onChange={(e) => setChapterName(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-3 text-white placeholder:text-slate-600 focus:ring-2 focus:ring-indigo-500"
                  placeholder="e.g. Chapter 4 - Climate"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">
                  Starting Page Number (Optional)
                </label>
                <input
                  type="number"
                  min="1"
                  value={startingPageOffset}
                  onChange={(e) => setStartingPageOffset(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-3 text-white focus:ring-2 focus:ring-indigo-500"
                  placeholder="1"
                />
              </div>
            </div>
          </div>

          <hr className="border-slate-800" />

          {/* Document Properties */}
          <div className="space-y-4">
            <h2 className="text-xl font-semibold text-white">
              2. Content Metadata & Upload
            </h2>

            <div>
              <label className="block text-sm font-medium text-slate-400 mb-2">
                File Upload (.pdf or .txt) (Required)
              </label>
              <input
                type="file"
                accept=".pdf,.txt"
                required
                onChange={handleFileChange}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-3 text-white file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 file:text-sm file:font-semibold file:bg-indigo-900 file:text-indigo-200 hover:file:bg-indigo-800"
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">
                  Title (Required)
                </label>
                <input
                  type="text"
                  required
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-3 text-white"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">
                  Source Type
                </label>
                <select
                  value={sourceType}
                  onChange={(e) => setSourceType(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-3 text-white"
                >
                  <option value="ncert">NCERT</option>
                  <option value="standard_book">Standard Book</option>
                  <option value="static">Static Notes</option>
                  <option value="dynamic">Current Affairs/Dynamic</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">
                  Edition (Optional)
                </label>
                <input
                  type="text"
                  value={edition}
                  onChange={(e) => setEdition(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-3 text-white"
                  placeholder="e.g., 2023-24"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">
                  Version (Optional)
                </label>
                <input
                  type="text"
                  value={sourceVersion}
                  onChange={(e) => setSourceVersion(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-3 text-white"
                  placeholder="e.g., v1.2"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">
                  ISBN (Optional)
                </label>
                <input
                  type="text"
                  value={isbn}
                  onChange={(e) => setIsbn(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-3 text-white"
                  placeholder="e.g., 978-3-16-148410-0"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-400 mb-2">
                  Publication Year (Optional)
                </label>
                <input
                  type="number"
                  value={year}
                  onChange={(e) => setYear(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-4 py-3 text-white"
                  placeholder="2024"
                />
              </div>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-4 px-6 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 font-bold text-white rounded-xl shadow-lg shadow-indigo-500/30 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading
              ? "Chunking Vectors... Please Wait..."
              : "Launch Direct Ingestion"}
          </button>
        </form>
      </div>
    </div>
  );
}
