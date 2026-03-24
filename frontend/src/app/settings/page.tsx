"use client";

import { motion } from "framer-motion";
import { Header } from "@/components/layout/Header";
import { BottomNav } from "@/components/layout/BottomNav";
import { ProjectSettings } from "@/components/settings/ProjectSettings";

export default function SettingsPage() {
  return (
    <>
      <Header />
      <motion.main
        className="flex-1 container mx-auto px-4 pb-24 md:pb-8 pt-6"
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
      >
        <ProjectSettings />
      </motion.main>
      <BottomNav />
    </>
  );
}
