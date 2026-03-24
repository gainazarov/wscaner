"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams } from "next/navigation";
import { motion } from "framer-motion";
import { Header } from "@/components/layout/Header";
import { BottomNav } from "@/components/layout/BottomNav";
import { ScanResult } from "@/components/scan/ScanResult";
import { LiveScanView } from "@/components/scan/LiveScanView";
import { api, Scan } from "@/lib/api";

export default function ScanPage() {
  const params = useParams();
  const scanId = params.id as string;
  const [scan, setScan] = useState<Scan | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchScan = useCallback(async () => {
    try {
      const data = await api.getScan(Number(scanId));
      setScan(data);
      setLoading(false);
    } catch (err) {
      setError("Failed to load scan");
      setLoading(false);
    }
  }, [scanId]);

  useEffect(() => {
    fetchScan();
  }, [fetchScan]);

  // Called when LiveScanView finishes — re-fetch scan to get completed state
  const handleScanComplete = useCallback(() => {
    // Small delay to let the DB save finish
    setTimeout(() => fetchScan(), 2000);
  }, [fetchScan]);

  const isLive = scan && (scan.status === "pending" || scan.status === "running");

  return (
    <>
      <Header />
      <motion.main
        className="flex-1 container mx-auto px-4 pb-24 md:pb-8 pt-6"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        {loading ? (
          <div className="space-y-4">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="skeleton h-20 rounded-xl" />
            ))}
          </div>
        ) : error ? (
          <div className="text-center py-20">
            <p className="text-red-400 text-lg">{error}</p>
          </div>
        ) : scan && isLive ? (
          <LiveScanView
            scanId={scan.id}
            domain={scan.domain}
            onComplete={handleScanComplete}
          />
        ) : scan ? (
          <ScanResult scan={scan} />
        ) : null}
      </motion.main>
      <BottomNav />
    </>
  );
}
