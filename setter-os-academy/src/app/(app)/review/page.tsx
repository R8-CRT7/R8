import { Suspense } from "react";
import ReviewCenter from "./ReviewCenter";

export default function Page() {
  return (
    <Suspense>
      <ReviewCenter />
    </Suspense>
  );
}
