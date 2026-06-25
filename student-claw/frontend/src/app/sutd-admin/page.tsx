/**
 * /sutd-admin — diagnostic dashboard (Requirement 1).
 * Server-gated: shows the token prompt until the admin cookie is valid.
 */

import { AdminDashboard } from "@/components/admin/AdminDashboard";
import { AdminLogin } from "@/components/admin/AdminLogin";
import { isAdminAuthed } from "@/lib/adminProxy";

export const dynamic = "force-dynamic";
export const metadata = { title: "SUTD_Admin" };

export default async function SutdAdminPage() {
  const authed = await isAdminAuthed();
  return authed ? <AdminDashboard /> : <AdminLogin />;
}
