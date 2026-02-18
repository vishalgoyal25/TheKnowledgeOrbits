/**
 * Comprehensive Footer - Multi-column layout with resources and navigation
 */

'use client';

import React from 'react';
import Link from 'next/link';
import { BookOpen, Github, Twitter, Linkedin, Facebook, Mail, MapPin, Phone } from 'lucide-react';

const footerLinks = {
    platform: [
        { label: 'Dashboard', href: '/dashboard' },
        { label: 'Generate Articles', href: '/generate' },
        { label: 'Take Quiz', href: '/assessment' },
        { label: 'Topic Mastery', href: '/topics' },
        { label: 'Current Affairs', href: '/current-affairs' },
    ],
    resources: [
        { label: 'UPSC Syllabus', href: '/resources/syllabus' },
        { label: 'Preparation Guide', href: '/blog/prep-guide' },
        { label: 'PYQ Analysis', href: '/resources/pyq' },
        { label: 'Study Timetable', href: '/resources/timetable' },
    ],
    company: [
        { label: 'About Us', href: '/about' },
        { label: 'Contact', href: '/contact' },
        { label: 'Careers', href: '/careers' },
        { label: 'Institutional Access', href: '/business' },
    ],
    legal: [
        { label: 'Privacy Policy', href: '/privacy' },
        { label: 'Terms of Service', href: '/terms' },
        { label: 'Cookie Policy', href: '/cookies' },
    ]
};

const socialLinks = [
    { icon: Twitter, href: '#', label: 'Twitter' },
    { icon: Github, href: '#', label: 'GitHub' },
    { icon: Linkedin, href: '#', label: 'LinkedIn' },
    { icon: Facebook, href: '#', label: 'Facebook' },
];

export default function Footer() {
    return (
        <footer className="bg-white border-t pt-16 pb-8">
            <div className="container mx-auto px-4">
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-12 mb-16">
                    {/* Brand Column */}
                    <div className="lg:col-span-2 space-y-6">
                        <Link href="/" className="flex items-center space-x-2">
                            <BookOpen className="h-8 w-8 text-blue-600" />
                            <span className="text-2xl font-bold text-gray-900 tracking-tight">
                                TheKnowledgeOrbits
                            </span>
                        </Link>
                        <p className="text-gray-500 max-w-sm text-sm leading-relaxed">
                            Empowering UPSC aspirants with AI-driven insights, personalized learning modules, and the most comprehensive knowledge orbits available. Master the syllabus with intelligence.
                        </p>
                        <div className="flex space-x-4">
                            {socialLinks.map((social) => (
                                <Link
                                    key={social.label}
                                    href={social.href}
                                    className="p-2 rounded-full bg-gray-50 text-gray-400 hover:bg-blue-50 hover:text-blue-600 transition-all"
                                    aria-label={social.label}
                                >
                                    <social.icon className="h-5 w-5" />
                                </Link>
                            ))}
                        </div>
                    </div>

                    {/* Links Columns */}
                    <div className="grid grid-cols-2 lg:grid-cols-3 lg:col-span-3 gap-8">
                        <div>
                            <h3 className="font-bold text-gray-900 mb-6 text-sm uppercase tracking-wider text-blue-600">Platform</h3>
                            <ul className="space-y-4">
                                {footerLinks.platform.map((link) => (
                                    <li key={link.label}>
                                        <Link href={link.href} className="text-gray-600 hover:text-blue-600 transition-colors text-sm">
                                            {link.label}
                                        </Link>
                                    </li>
                                ))}
                            </ul>
                        </div>

                        <div>
                            <h3 className="font-bold text-gray-900 mb-6 text-sm uppercase tracking-wider text-green-600">Resources</h3>
                            <ul className="space-y-4">
                                {footerLinks.resources.map((link) => (
                                    <li key={link.label}>
                                        <Link href={link.href} className="text-gray-600 hover:text-blue-600 transition-colors text-sm">
                                            {link.label}
                                        </Link>
                                    </li>
                                ))}
                            </ul>
                        </div>

                        <div>
                            <h3 className="font-bold text-gray-900 mb-6 text-sm uppercase tracking-wider text-purple-600">Legal</h3>
                            <ul className="space-y-4">
                                {footerLinks.legal.map((link) => (
                                    <li key={link.label}>
                                        <Link href={link.href} className="text-gray-600 hover:text-blue-600 transition-colors text-sm">
                                            {link.label}
                                        </Link>
                                    </li>
                                ))}
                            </ul>
                        </div>
                    </div>
                </div>

                {/* Bottom Bar */}
                <div className="pt-8 border-t flex flex-col md:flex-row justify-between items-center gap-4">
                    <div className="text-sm text-gray-500">
                        © {new Date().getFullYear()} TheKnowledgeOrbits. All rights reserved.
                        <span className="mx-2 hidden md:inline">|</span>
                        Made with ❤️ for UPSC Aspirants.
                    </div>

                    <div className="flex items-center gap-6 text-xs text-gray-400">
                        <div className="flex items-center gap-2">
                            <Mail className="h-3 w-3" />
                            support@knowledgeorbits.com
                        </div>
                        <div className="flex items-center gap-2">
                            <MapPin className="h-3 w-3" />
                            New Delhi, India
                        </div>
                    </div>
                </div>
            </div>
        </footer>
    );
}
