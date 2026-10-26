import json
BANK = """Normal stress ; σ = {F|A} ; pa,n/m2,mpa ; Pa (N/m²) ; σ@Pa,MPa|F@N|A@m²
Kinetic energy ; KE = {1|2} × m × v² ; j,joule ; J (joule) ; KE@J|m@kg|v@m/s
Ohm's law ; V = I × R ; v,volt ; V (volt) ; V@V|I@A|R@Ω
Power in AC circuit ; P = V_rms × I_rms × cosφ ; w,watt ; W (watt) ; P@W|V_rms@V|I_rms@A
Quadratic root ; x = {−b + √{b² + 4 × a × c}|2 × a} ; ; ;
Resonant frequency ; f = {1|2 × π × √{L × C}} ; hz,hertz ; Hz (hertz) ; f@Hz|L@H|C@F
Parallel resistance (nested) ; R = {1|{1|R₁} + {1|R₂} + {1|R₃}} ; ω,ohm ; Ω (ohm) ; R@Ω|R₁@Ω|R₂@Ω|R₃@Ω
Euler buckling load ; P_cr = {π² × E × I|K² × L²} ; n ; N ; P_cr@N|E@Pa|I@m⁴|K@|L@m
Max shear stress in a solid circular shaft under torsion ; τ = {16 × T|π × d³} ; pa,mpa ; Pa ; τ@Pa|T@N·m|d@m"""
def data():
    return {"v":1,"t":[{"n":"Sample EE","t":BANK,"f":""}],"f":[],"c":{},"r":{},"l":"medium","s":0,"ts":1}
if __name__=="__main__":
    print(json.dumps(data())[:200])
