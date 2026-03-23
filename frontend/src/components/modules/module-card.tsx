"use client";

import Link from "next/link";
import { Module } from "@/lib/types";
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Layers } from "lucide-react";

interface ModuleCardProps {
  module: Module;
}

export default function ModuleCard({ module }: ModuleCardProps) {
  return (
    <Link href={`/modules/${module.id}`}>
      <Card className="h-full transition-all hover:shadow-lg hover:-translate-y-1 hover:border-blue-300">
        <CardHeader>
          <div className="flex items-start justify-between gap-2">
            <CardTitle className="text-lg line-clamp-2 flex-1 text-slate-900">
              {module.name}
            </CardTitle>
          </div>
        </CardHeader>

        <CardContent>
          <p className="text-sm text-slate-600 line-clamp-3 mb-4">
            {module.description ||
              "Explore all categorized syllabus topics naturally grouped inside this module map."}
          </p>
        </CardContent>

        <CardFooter className="text-sm">
          <div className="flex items-center gap-4 w-full border-t pt-4 border-slate-50">
            <div className="flex items-center gap-1.5 text-blue-600 font-bold uppercase tracking-widest text-[11px]">
              <Layers className="h-4 w-4" />
              <span>Browse Topics &rarr;</span>
            </div>
          </div>
        </CardFooter>
      </Card>
    </Link>
  );
}
