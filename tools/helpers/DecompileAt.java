// Decompile selected functions without running full auto-analysis. Args: output file, then hex addresses.
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import java.io.PrintWriter;

public class DecompileAt extends GhidraScript {
    @Override
    public void run() throws Exception {
        String[] a = getScriptArgs();
        PrintWriter out = new PrintWriter(a[0], "UTF-8");
        DecompInterface di = new DecompInterface();
        di.openProgram(currentProgram);
        for (int i = 1; i < a.length; i++) {
            Address ad = toAddr(Long.parseUnsignedLong(a[i], 16));
            out.println("==== " + ad);
            try {
                Function f = getFunctionAt(ad);
                if (f == null) { disassemble(ad); f = createFunction(ad, null); }
                if (f == null) { out.println("no function"); continue; }
                out.println("// " + f.getName() + " body " + f.getBody());
                DecompileResults r = di.decompileFunction(f, 120, monitor);
                out.println(r.decompileCompleted() ? r.getDecompiledFunction().getC() : ("decompile failed: " + r.getErrorMessage()));
            } catch (Exception e) {
                out.println("error: " + e);
            }
        }
        out.close();
    }
}
