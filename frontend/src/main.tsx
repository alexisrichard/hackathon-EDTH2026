import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles/app.css";

// NOTE: no StrictMode — its dev double-mount races maplibre's async style
// load (map.remove() on the ghost instance wedges tile loading). The map
// lifecycle is handled explicitly in MapView.
ReactDOM.createRoot(document.getElementById("root")!).render(<App />);
