import Link from 'next/link';

export default function Navigation() {
  return (
    <nav>
      <Link href="/dashboard">Dashboard</Link>
      <Link href="/notebook">My Notebook</Link>
      <Link href="/bookmarks">Bookmarks</Link>
    </nav>
  );
}
