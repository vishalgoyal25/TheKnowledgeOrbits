"use client";
import { useState } from "react";
import { useAuth } from "@/lib/auth/useAuth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Alert } from "@/components/ui/alert";

export default function RegisterForm() {
  const { register } = useAuth();
  const [formData, setFormData] = useState({
    email: "",
    password: "",
    password_confirm: "",
    full_name: "",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");

    if (formData.password !== formData.password_confirm) {
      setError("Passwords do not match");
      return;
    }

    setLoading(true);
    try {
      await register(formData);
    } catch (err: any) {
      setError(err.response?.data?.message || "Registration failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && <Alert variant="destructive">{error}</Alert>}

      <Input
        placeholder="Full Name"
        value={formData.full_name}
        onChange={(e) =>
          setFormData({ ...formData, full_name: e.target.value })
        }
      />
      <Input
        type="email"
        placeholder="Email"
        value={formData.email}
        onChange={(e) => setFormData({ ...formData, email: e.target.value })}
        required
      />
      <Input
        type="password"
        placeholder="Password"
        value={formData.password}
        onChange={(e) => setFormData({ ...formData, password: e.target.value })}
        required
      />
      <Input
        type="password"
        placeholder="Confirm Password"
        value={formData.password_confirm}
        onChange={(e) =>
          setFormData({ ...formData, password_confirm: e.target.value })
        }
        required
      />

      <Button type="submit" className="w-full" disabled={loading}>
        {loading ? "Creating account..." : "Create Account"}
      </Button>
    </form>
  );
}
