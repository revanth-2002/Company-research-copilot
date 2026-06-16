import { SignIn } from "@clerk/clerk-react";

export default function Login() {
  return (
    <div className="auth-page">
      <SignIn
        forceRedirectUrl="/"
        appearance={{
          variables: { fontSize: "1.1rem", spacingUnit: "1.1rem" },
        }}
      />
    </div>
  );
}