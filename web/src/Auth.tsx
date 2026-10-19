import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Eye,
  EyeOff,
  ArrowRight,
  MapPin,
  Compass,
  ArrowUpRight,
} from "lucide-react";
import { Button } from "./components/ui/button";
import { Dialog } from "./components/ui/dialog";
import { api, errorMessage, setCsrf } from "./lib/api";
import logo from "../../assets/images/sdu_30_logo.png";
const schema = z.object({
  sdu_id: z.string().regex(/^\d{9}$/, "Enter your 9-digit SDU ID."),
  password: z.string().min(8, "Use at least 8 characters."),
  full_name: z.string(),
  confirm: z.string(),
});
type Fields = z.infer<typeof schema>;
export function Auth({ onSuccess }: { onSuccess: () => void }) {
  const [register, setRegister] = useState(false),
    [visible, setVisible] = useState(false),
    [error, setError] = useState(""),
    [pending, setPending] = useState(false),
    [demo, setDemo] = useState(false);
  const {
    register: field,
    handleSubmit,
    formState: { errors },
    setError: fieldError,
    reset,
  } = useForm<Fields>({
    resolver: zodResolver(schema),
    defaultValues: { sdu_id: "", password: "", full_name: "", confirm: "" },
  });
  async function submit(values: Fields) {
    if (register && values.full_name.trim().length < 2) {
      fieldError("full_name", { message: "Enter your full name." });
      return;
    }
    if (register && values.password !== values.confirm) {
      fieldError("confirm", { message: "Passwords do not match." });
      return;
    }
    setPending(true);
    setError("");
    try {
      const result = await api.post(
        "/auth/" + (register ? "register" : "login"),
        {
          sdu_id: values.sdu_id,
          password: values.password,
          ...(register ? { full_name: values.full_name } : {}),
        },
      );
      setCsrf(result.data.csrf_token);
      onSuccess();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setPending(false);
    }
  }
  async function guest() {
    setPending(true);
    setError("");
    try {
      const result = await api.post("/auth/guest");
      setCsrf(result.data.csrf_token);
      onSuccess();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setPending(false);
    }
  }
  return (
    <main className="auth-page">
      <section className="auth-story">
        <img
          src={logo}
          className="auth-logo"
          alt="SDU University 30th anniversary"
        />
        <div className="story-copy">
          <span className="eyebrow gold">
            A LITTLE GUIDANCE GOES A LONG WAY
          </span>
          <h1>
            Your campus.
            <br /> A little closer.
          </h1>
          <p>
            Find your classroom, discover a quiet corner, and take the next turn
            with confidence.
          </p>
          <div className="story-features">
            <span>
              <MapPin size={18} /> Explore campus
            </span>
            <span>
              <Compass size={18} /> Find your way
            </span>
          </div>
        </div>
        <div className="story-bottom">
          <span>SDU CAMPUS ASSISTANT</span>
          <span>Built for our campus community ↗</span>
        </div>
        <div className="decor decor-one" />
        <div className="decor decor-two" />
      </section>
      <section className="auth-form-wrap">
        <div className="auth-topline">
          <span>SEMESTER PROJECT</span>
          <span className="gold-line" />
        </div>
        <div className="auth-form">
          <span className="eyebrow">WELCOME TO YOUR CAMPUS</span>
          <h2>{register ? "Make yourself at home." : "Good to see you."}</h2>
          <p className="muted">
            {register
              ? "Create an account to save places and plan your day."
              : "Sign in to pick up where you left off."}
          </p>
          <form onSubmit={handleSubmit(submit)} noValidate>
            {register && (
              <label>
                Full name
                <input
                  autoComplete="name"
                  placeholder="Your full name"
                  {...field("full_name")}
                />
                {errors.full_name && (
                  <small className="field-error">
                    {errors.full_name.message}
                  </small>
                )}
              </label>
            )}
            <label>
              SDU ID
              <input
                inputMode="numeric"
                autoComplete="username"
                maxLength={9}
                placeholder="e.g. 240103049"
                {...field("sdu_id")}
              />
              {errors.sdu_id && (
                <small className="field-error">{errors.sdu_id.message}</small>
              )}
            </label>
            <label>
              Password
              <div className="password-field">
                <input
                  type={visible ? "text" : "password"}
                  placeholder="At least 8 characters"
                  autoComplete={register ? "new-password" : "current-password"}
                  {...field("password")}
                />
                <button
                  type="button"
                  aria-label={visible ? "Hide password" : "Show password"}
                  onClick={() => setVisible(!visible)}
                >
                  {visible ? <EyeOff size={18} /> : <Eye size={18} />}
                </button>
              </div>
              {errors.password && (
                <small className="field-error">{errors.password.message}</small>
              )}
            </label>
            {register && (
              <label>
                Confirm password
                <input
                  type={visible ? "text" : "password"}
                  autoComplete="new-password"
                  placeholder="Repeat your password"
                  {...field("confirm")}
                />
                {errors.confirm && (
                  <small className="field-error">
                    {errors.confirm.message}
                  </small>
                )}
              </label>
            )}
            {error && (
              <div role="alert" className="error-box">
                {error}
              </div>
            )}
            <Button className="w-full mt-2" disabled={pending} type="submit">
              {pending
                ? "Connecting…"
                : register
                  ? "Create account"
                  : "Sign in"}
              <ArrowRight size={17} />
            </Button>
          </form>
          <p className="auth-switch">
            {register ? "Already have an account?" : "New around here?"}{" "}
            <button
              onClick={() => {
                setRegister(!register);
                setError("");
                reset();
              }}
            >
              {register ? "Sign in" : "Create an account"}
            </button>
          </p>
          <div className="or-divider">
            <span />
            or explore first
            <span />
          </div>
          <Button
            variant="outline"
            className="w-full"
            onClick={guest}
            disabled={pending}
          >
            Continue as guest <ArrowUpRight size={16} />
          </Button>
          <p className="guest-note">
            Maps, campus services and routes. No account needed.
          </p>
          <button className="demo-link" onClick={() => setDemo(true)}>
            Demo access
          </button>
        </div>
        <p className="auth-footer">
          A student course project · No university SSO required
        </p>
      </section>
      <Dialog
        open={demo}
        onOpenChange={setDemo}
        title="Try a campus perspective"
        description="Local presentation accounts. Enter the credentials in the sign-in form."
      >
        <div className="demo-accounts">
          <p>
            Student <code>240103049</code>
          </p>
          <p>
            Teacher <code>240000001</code>
          </p>
          <p>
            Administrator <code>240000002</code>
          </p>
          <p>
            Shared demo password <code>Campus123!</code>
          </p>
        </div>
      </Dialog>
    </main>
  );
}
