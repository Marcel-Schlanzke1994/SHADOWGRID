import { z } from "zod";

export const loginSchema = z.object({ email: z.string().email(), password: z.string().min(1), totp_code: z.string().regex(/^\d{6}$/).optional() });
export const registerSchema = z.object({ email: z.string().email(), display_name: z.string().min(2).max(40), password: z.string().min(12).max(128).regex(/[a-z]/).regex(/[A-Z]/).regex(/\d/), terms_accepted: z.literal(true) });
export const operationSchema = z.object({ operation_type: z.string(), district_id: z.string().uuid(), specialist_id: z.string().uuid(), target: z.string().min(2).max(120), budget: z.number().min(1000).max(1_000_000), intelligence_spend: z.number().min(0).max(100), risk_posture: z.enum(["cautious", "balanced", "aggressive"]), secrecy: z.number().min(0).max(100) });
