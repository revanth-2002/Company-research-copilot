import { SignUp } from "@clerk/clerk-react";

export default function Signup() {
  return (
    <div className="auth-page">
      <SignUp
        forceRedirectUrl="/"
        appearance={{
          variables: { fontSize: "1.1rem", spacingUnit: "1.1rem" },
        }}
      />
    </div>
  );
}