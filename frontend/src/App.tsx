import { createBrowserRouter, RouterProvider } from "react-router-dom";
import { applicationRoutes } from "./routes";

const router = createBrowserRouter(applicationRoutes, { future: { v7_relativeSplatPath: true } });
export default function App() {
  return <RouterProvider router={router} future={{ v7_startTransition: true }} />;
}
