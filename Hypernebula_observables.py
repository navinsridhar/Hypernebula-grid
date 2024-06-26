#----------------------------------------------------------------------------------------------------
#Hypernebula observables
#Version:   3rd April 2024
#Paper:     Sridhar & Metzger (2022); The Astrophysical Journal, Volume 937, Issue 1, id.5, 22 pp.
#----------------------------------------------------------------------------------------------------

import os
# os.chdir('/global/u1/n/nsridhar/cori/cooling/ions/comp5.my16k.nocool.sig3.bz1e-1.ppc4.ntimes32_ion7/output/')

# Python modules
import warnings
warnings.filterwarnings("ignore")

import h5py
import scipy
from scipy import *
from scipy.fftpack import fft, fftfreq
# from scipy.special import kn
from scipy import signal
# from scipy.fft import fft, fftfreq
import glob
import numpy as np
import numpy.ma as ma
import math
import cmath
from scipy.special import kv    #Modified Bessel function of the second kind
from datetime import datetime
import pickle
import Constants as C
import scipy.special as special
import scipy.integrate as integrate
import codecs
import sys
import Synchrotron


#two phase expansion
def relativistic_Maxwellian(gamma,gamma_i):
    beta = (1.0 - 1.0/gamma)**0.5
    f = gamma**2*beta*np.exp(-gamma/gamma_i)/(gamma_i*special.kv(2,1.0/gamma_i))
    return f


# Hypernebula parameters (Sridhar & Metzger 2022):
#-------------------------------------------------
# Fiducial
alpha       = 0.0              #0.0 for fiducial ULX injection   
alpha_shock = 0.8
epsilon_e   = 0.5
mu          = 1.38             #Mean molecular weight of neutral ISM
n_0         = 10                #density of the ISM surrounding a massive star; in units of 1/cc
rho_ISM     = mu*n_0*C.mp
Mstar       = 30.0*C.Msun

sigma   = 1
v_w     = 0.03*C.c             
v_j     = 0.5*C.c
Mdot_w  = 5e3*C.Mdot_Edd    #1e5*C.Mdot_Edd in paper
# Mdot_w  = 2.0 * 2.8e40 / (v_w**2)     #Fixing the wind luminosity to 2.8e40 (fits 121102's spectrum) to change Mdot_w and v_w
L_w     = 0.5*Mdot_w*v_w**2
eta     = 1               #Ratio of the wind luminosity to the jet luminosity

t0       = 0.1*C.yr
t_active = Mstar/Mdot_w; t_active_end = True
E_tot    = L_w*t_active
Mej      = Mdot_w*t_active      #=Mstar, usually
chi      = epsilon_e  * C.mp * C.c**2 * (v_j/C.c)**2

r_cs    = np.sqrt(L_w/(2*np.pi*rho_ISM*v_w**3))
t_free  = r_cs/v_w

gi       = (chi/(C.me*C.c**2))/2.0     #Lorentz factor of the electrons heated at the shock that enter the nebula. 


# Magnetar flare parameters (Margalit & Metzger 2018)
#-------------------------------------------------
# chi     = 0.2*1e9*C.eV   #xi**(-1) # erg per particle
# Mej     = 10.*C.Msun
# sigma   = 1e-1

# #Model A (This would correspond to an Mdot = 1.3e8 Mdot_Edd)
# alpha   = 1.3             #1.7 #1.1
# t0      = 0.2*C.yr       #0.5*C.yr #1.0*C.yr #300.0*C.yr #100.0*C.yr
# E_tot   = 5e50            #For 1e5 Mdot_Edd
# vej     = 0.01*C.c


# #Model B
# alpha   = 1.3             #1.7 #1.1
# t0      = 0.6*C.yr       #0.5*C.yr #1.0*C.yr #300.0*C.yr #100.0*C.yr
# E_tot   = 5e50            #For 1e5 Mdot_Edd
# vej     = 1e8

# #Model C
# alpha   = 1.83             #1.7 #1.1
# t0      = 0.2*C.yr       #0.5*C.yr #1.0*C.yr #300.0*C.yr #100.0*C.yr
# E_tot   = 4.9e51            #For 1e5 Mdot_Edd
# vej     = 9e8
# #-------------------------------------------------

print('L_w      = {:.3g}\t erg/s'.format(L_w))
print('E_tot    = {:.3g}\t erg'.format(E_tot))
print('t_free   = {:.3g}\t\t yr'.format(t_free/C.yr))
print('t_active = {:.3g}\t yr'.format(t_active/C.yr))
print('\chi     = {:.3g}'.format(chi))
print('\gammai  = {:.3g}'.format(gi))

#CHANGE LINE 572 (SAVED FILE NAME)


#---------------------------------

const_vn = False
if const_vn:
    cont_vn_factor1 = 0.0
    cont_vn_factor2 = np.inf
else:
    cont_vn_factor1 = 1e0
    cont_vn_factor2 = 1e0

def rho_SN(r,t):
    Mej    = Mdot_w * t                                          #Comment for Magnetar flares
#     rho    = 3.0*Mej/(4.0*np.pi*(v_w*t)**3)
    rho    = 3.0*Mej/(4.0*np.pi*r**3)
    return rho

#Smoothening hyperbolic tangent function
def tanh(time, t_cr, wide_factor=0.05):
    return 0.5 * (1.+np.tanh(wide_factor*(time-t_cr)))

if alpha==0.0:
    Edot_of_t = lambda t: (E_tot/t_active)
    if t_active_end == True:
        L_w_off   = lambda t: L_w * (1 - tanh(t, t_active))         #Turning off the engine at t=t_active
        E_of_t    = lambda t: E_tot*(t/t_active) * (1 - tanh(t, t_active)) + E_tot * tanh(t, t_active)
    else:
        E_of_t = lambda t: E_tot*(t/t_active)
#     Edot_of_t = lambda t: (E_tot/t0)
#     E_of_t = lambda t: E_tot*(t/t0)
    eps=5e-4
#     t = t0*(eps+(1-eps)*10**np.linspace(np.log10(eps),0,1000))
    t = t0*(1.0+10**np.linspace(-3,7.3,1000)) #t0*(1.0+10**np.linspace(-3,2.3,1e3))
elif alpha>1.0:
    
#     #------------------------------------------------------
#     Mdot_w = lambda t: Mdot_w * (t/t0)**alpha
#     v_w    = lambda t: v_w * (t/t0)**(-alpha/2.)
#     L_w     = 0.5*Mdot_w*v_w**2
#     E_tot    = L_w*t_active
#     #------------------------------------------------------
    
    Edot_of_t = lambda t: (alpha-1.0)*(E_tot/t0)*(t/t0)**(-alpha)
    #E_of_t = lambda t: integrate.quad( Edot_of_t, t0,t )[0]
    E_of_t = lambda t: E_tot*(1.0-(t/t0)**(1.0-alpha))
    t = t0*(1.0+10**np.linspace(-3,7.3,1000)) #t0*(1.0+10**np.linspace(-3,2.3,1e3))
elif alpha<0.0:                                                                                               #WHY?
    from scipy import signal
    frac = 0.99
    freq = 10.0/t0
    #Edot_of_t = lambda t: (E_tot/t0)*frac
    def Edot_of_t(t):
        #return (E_tot/t0)/frac if t<t0*frac else 0.0
        return 0.5*(signal.square(2*np.pi*freq*t, duty=(frac))+1.0)*(E_tot/t0)/frac
    Edot_of_t = np.vectorize(Edot_of_t)
    eps=1e-2
    t = t0*(eps+(1-eps)*10**np.linspace(np.log10(eps),0,1000))
    #E_of_t = lambda t: integrate.quad( Edot_of_t, 0.0,t )[0]
    def E_of_t(t):
        #return E_tot*(t/t0)/frac if t<t0*frac else E_tot
        N = np.floor(t*freq)
        N = N + (1.0 if (freq*t-N)>frac else 0.0)
        return N*(E_tot/t0)/freq + Edot_of_t(t)*(t-N/freq)
    E_of_t = np.vectorize(E_of_t)

t_free_index   = np.argmin(abs(t-t_free))
t_active_index = np.argmin(abs(t-t_active))

gamma       = 10**np.linspace(0,np.log10(50*gi),120)
ng          = np.zeros((len(t),len(gamma)))             # dN(gamma,t)/dgamma
beta        = (1.0 - 1.0/gamma)**0.5


# calculate synchrotron spectrum/light-curve
Fintegrand = lambda y: special.kv(5.0/3.0,y)
F_synchrotron = lambda x: x*integrate.quad( Fintegrand, x,np.inf )[0]
xary=10**np.linspace(-2,2,1000); Fary=np.zeros_like(xary);
for i in range(len(Fary)):
    Fary[i] = F_synchrotron(xary[i])
def F_synchrotron(x):
    F = 10**np.interp(np.log10(x), np.log10(xary),np.log10(Fary), left=0.0,right=0.0)
    F[x<xary[0]] = Fary[0]*(x[x<xary[0]]/xary[0])**(1.0/3.0)
    F[x>xary[-1]] = Fary[-1]*(x[x>xary[-1]]/xary[-1])**0.5*np.exp(-(x[x>xary[-1]]-xary[-1]))
    return F

def Synchrotron_of_gammae(gamma,ng,B,nu,R=np.inf):                         #an easy way to calculate L_nu without actually solving for absorption coefficient
    flag=False
    nuc = (C.q*B/(2*np.pi*C.me*C.c))*gamma**2 # cyclotron frequency of each electron Lorentz factor
    #if nu==-1:
    #    nu=nuc
    #    flag=True
    Lnu = np.zeros_like(nu)
    Te = gamma*C.me*C.c**2/(3*C.kb) # effective electron temperature
    Lnu_T = np.zeros_like(nu)

    for i in range(len(nu)):
        Pnu = np.zeros_like(gamma)
        Pnu = 2*np.pi*(C.q**3*B/(3.0**0.5*np.pi*C.me*C.c**2))*F_synchrotron(nu[i]/nuc) # contribution of each electron Lorentz factor to emitted power at frequency nu
        Lnu[i] = np.trapz( Pnu*ng, x=gamma ) # sum over entire electron distribution
        Lnu_T[i] = np.interp(nu[i], nuc,4*np.pi*R**2*(2*C.kb*Te*nuc**2/C.c**2)) # Rayleigh-Jeans "thermal" luminosity

    Lnu = (4.0*np.pi*R**3/3.0)*Lnu

    fctr = (Lnu_T/Lnu); fctr[fctr>1]=1.0
    Lnu[Lnu>Lnu_T] = Lnu_T[Lnu>Lnu_T] # if flux > black-body then optically thick => use black-body (approximate treatment of self-absorption)

    if flag:
        res = [Lnu,nu,fctr]
    else:
        res = Lnu
    return res

def fast_Synchrotron_of_gammae(gamma,ng,B,R=np.inf):                          #for calculating synchrotron self-absorption factor
    nuc = (C.q*B/(2*np.pi*C.me*C.c))*gamma**2 # cyclotron frequency of each electron Lorentz factor
    Te = gamma*C.me*C.c**2/(3*C.kb) # effective electron temperature
    Pnuc = 2*np.pi*(C.q**3*B/(3.0**0.5*np.pi*C.me*C.c**2))*0.6514 #F_synchrotron(nuc/nuc) # contribution of each electron Lorentz factor to emitted power at frequency nu
    Lnuc = Pnuc*(4.0*np.pi*R**3/3.0)*ng*gamma #np.trapz( Pnuc*Ng, x=gamma ) # sum over entire electron distribution
    Lnuc_T = 4*np.pi*R**2*(2*C.kb*Te*nuc**2/C.c**2) # Rayleigh-Jeans "thermal" luminosity

    fctr = (Lnuc_T/Lnuc); fctr[fctr>1]=1.0; fctr[fctr<0]=0.0;
    Lnuc[Lnuc>Lnuc_T] = Lnuc_T[Lnuc>Lnuc_T] # if flux > black-body then optically thick => use black-body (approximate treatment of self-absorption)

    Ltot = np.trapz( Lnuc, x=nuc )

    res = [Lnuc,nuc,fctr,Ltot]
    return res

#The following two definitions are not required here. Called from the Synchrotron module.
'''
def Pnu_synchrotron(gamma,B,nu):
    nuc = (C.q*B/(2*np.pi*C.me*C.c))*gamma**2
    #Pnu = np.zeros_like(nu)
    #for i in range(len(nu)):
    #    Pnu = 2*np.pi*(C.q**3*B/(3.0**0.5*np.pi*C.me*C.c**2))*F_synchrotron(nu[i]/nuc)
    Pnu = 2*np.pi*(C.q**3*B/(3.0**0.5*np.pi*C.me*C.c**2))*F_synchrotron(nu/nuc)
    return Pnu

def alphanu_synchrotron(gamma,ng,B,nu):
    alphanu = np.zeros_like(nu)
    for i in range(len(nu)):
        alphanu[i] = -(8*np.pi*C.me*nu[i]**2)**(-1)*np.trapz( gamma**2*Pnu_synchrotron(gamma,B,nu[i])*np.diff(ng/gamma**2)/np.diff(gamma), x=gamma )
    return alphanu
'''

# start integration

x  = np.log(gamma)
dx = x[1:]-x[:-1]

Ngi_arry = relativistic_Maxwellian(gamma,gi)

# Ngi_arry=np.zeros_like(gamma); 
# Ngi_arry[gamma==gamma[gamma>3*gi][0]]=1.0; 
# Ngi_arry=Ngi_arry/np.trapz( Ngi_arry, x=gamma ) # hack for approximate delta-function injection
Ne = eta * E_of_t(t)/(chi*(1.0+sigma))
Ne0 = Ne[0]
Ne  = Ne-Ne0

gdot_ad  = np.zeros_like(ng)
gdot_syn = np.zeros_like(ng)
gdot_br  = np.zeros_like(ng)
gdot_IC  = np.zeros_like(ng)

Rn = np.zeros_like(t)
vn = np.zeros_like(t)
Mn = np.zeros_like(t)
Pn = np.zeros_like(t)
Bn = np.zeros_like(t)
EB = np.zeros_like(t)
# EB = sigma*E_of_t(t)/(1.0+sigma)                                #Uncomment for magnetar flare
# EB0 = EB[0]                                                     #Uncomment for magnetar flare

Rsh_free = v_w * t 
Rn_free = Rsh_free * (2.*v_w*eta / (3.*v_j))**0.5
vn_free = v_w * (2.*v_w*eta / (3.*v_j))**0.5

R_fs = alpha_shock * ((E_of_t(t)/t)*t**3./rho_ISM)**0.2
# R_fs = alpha_shock * (L_w*t**3./rho_ISM)**0.2
v_fs = 0.6 * R_fs/t
Rn_ssimilar = R_fs * (2.*v_fs*eta / (3.*v_j))**0.5
vn_ssimilar = v_fs * (2.*v_fs*eta / (3.*v_j))**0.5

#smoothening Rn and Vn across t_free using a hyperbolic tangent defined above
Rn  = Rn_free * (1 - tanh(t, t_free)) + Rn_ssimilar * tanh(t, t_free)
vn  = vn_free * (1 - tanh(t, t_free)) + vn_ssimilar * tanh(t, t_free)
Rsh = Rsh_free * (1 - tanh(t, t_free)) + R_fs * tanh(t, t_free)

Msh_free     = Mdot_w * t
Msh_ssimilar = rho_ISM * (4.*np.pi*Rsh**3./3.)
Msh          = Msh_free * (1 - tanh(t, t_free)) + Msh_ssimilar * tanh(t, t_free)

Mn   = rho_SN(Rn,t)*(4.*np.pi*Rn**3./3.)
Pn   = E_of_t(t)/(4.*np.pi*Rn**3./3.)
Bn   = np.sqrt(6.*sigma*eta*E_of_t(t)/Rn**3.)
# Pn   =L_w*t/(4.*np.pi*Rn**3./3.)
# Bn   = np.sqrt(6.*sigma*eta*L_w*t/Rn**3.)
EB   = (Bn**2./(8.*np.pi)) * (4.*np.pi*Rn**3./3.)


Rn_tmp = Rn[0]
vn_tmp = vn[0]
Mn_tmp = Mn[0]
Pn_tmp = Pn[0]
Bn_tmp = Bn[0]
Ne_tmp = Ne[0]
EB_tmp = EB[0]
ng_tmp = ng[0,:]
t_tmp  = t[0]

#res = Synchrotron_of_gammae(gamma,Ng_tmp,(6.0*EB_tmp/(Rn_tmp**3))**0.5,nu=-1,R=Rn_tmp)
res = fast_Synchrotron_of_gammae(gamma,ng_tmp,(6.0*EB_tmp/(Rn_tmp**3))**0.5,R=Rn_tmp) 
fctr_tmp = res[2]  #1.0
L_tmp = res[3]  #0.0   

import time
runtime = time.time()

n = 0
loop_count = 0
loop_max = 1e10 #2e6
# final_time = 1.1e6 #year
final_time = 1.1e6 #year

while (n<len(t)-1) and (loop_count<loop_max) and (t_tmp/C.yr<final_time):
    Rn_tmp = Rn[n]     #use this line only while evolving the self-similar phase.
    vn_tmp = vn[n]     #use this line only while evolving the self-similar phase.
    Mn_tmp = Mn[n]     #use this line only while evolving the self-similar phase.
    Pn_tmp = Pn[n]     #use this line only while evolving the self-similar phase.
#     EB_tmp = EB[n]     
    Rdot = vn_tmp
    
    gdot_ad_tmp  = (1.0/3.0)*beta**2*gamma*( 3.0*vn_tmp/Rn_tmp )
    gdot_syn_tmp = fctr_tmp*(C.sigT/(np.pi*C.me*C.c))*beta**2*gamma**2*EB_tmp/Rn_tmp**3
    gdot_br_tmp  = (5.0/6.0)*C.c*C.sigT*(1.0/137.0)*(3.0*Ne_tmp/(4.0*np.pi*Rn_tmp**3))*(gamma**1.2)*2.0 # the factor 2 at the end approximates Z*(Z+1)/A for H (it would be ~0.5 for heavy ions)
    gdot_IC_tmp  = (4*C.sigT/(3*C.me*C.c))*beta**2*gamma**2*(L_tmp/(4*np.pi*C.c*Rn_tmp**2))
    gdot = -(gdot_ad_tmp + gdot_syn_tmp + gdot_IC_tmp + gdot_br_tmp)


#     Rdot = vn_tmp      #Only use this line while evolving the free expansion phase.
    vdot = cont_vn_factor1*(4*np.pi*Rn_tmp**2/Mn_tmp)*( Pn_tmp - rho_SN(Rn_tmp,t_tmp)*( vn_tmp - Rn_tmp/t_tmp )**2 )
    Mdot = cont_vn_factor1*4*np.pi*Rn_tmp**2*rho_SN(Rn_tmp,t_tmp)*( vn_tmp - Rn_tmp/t_tmp )
    Pdot = cont_vn_factor1*( Edot_of_t(t_tmp)/(4*np.pi*Rn_tmp**3) - 4.*Pn_tmp*vn_tmp/Rn_tmp )
    dt   = min( 0.5*np.min((gamma[1:]-gamma[:-1])/np.abs(gdot[1:])), 0.5*np.abs(Rn_tmp/Rdot), cont_vn_factor2*0.5*np.abs(vn_tmp/vdot), cont_vn_factor2*0.5*np.abs(Mn_tmp/Mdot), cont_vn_factor2*0.5*np.abs(Pn_tmp/Pdot), 0.5*t_tmp, t[n+1]-t_tmp  ) 

    t_tmp  = t_tmp + dt
    Ne_old = Ne_tmp
    Ne_tmp = E_of_t(t_tmp)/(chi*(1.0+sigma)) - Ne0

    EB_old = EB_tmp
#     EB_tmp = max( EB_old - dt*(vn_tmp/Rn_tmp)*EB_old + sigma*(E_of_t(t_tmp)-E_of_t(t_tmp-dt))/(1.0+sigma) , 0.0 )
    EB_tmp = max( EB_old - dt*(vn_tmp/Rn_tmp)*EB_old + eta*sigma*(E_of_t(t_tmp)-E_of_t(t_tmp-dt))/(1.0+sigma) , 0.0 ) #Check this case.

    ng_old = ng_tmp
    j=np.arange(0,len(gamma)-1)
    ng_tmp[j] = ng_old[j] - (dt/dx[j])*np.exp(-x[j])*( gdot[j+1]*ng_old[j+1]-gdot[j]*ng_old[j] ) + dt*(-3.*Rdot/Rn_tmp)*ng_old[j] + (Ne_tmp-Ne_old)*Ngi_arry[j]/(4.0*np.pi*Rn_tmp**3/3.0) # upwind differencing

    j=len(gamma)-1   # boundary conditions at end
    ng_tmp[j] = ng_old[j] - ( ng_tmp[j-1]-ng_old[j-1] ) + dt*(-3.*Rdot/Rn_tmp)*ng_old[j] + (Ne_tmp-Ne_old)*Ngi_arry[j]/(4.0*np.pi*Rn_tmp**3/3.0)

    Rn_tmp = Rn_tmp + dt*Rdot
    vn_tmp = vn_tmp + dt*vdot
    Mn_tmp = Mn_tmp + dt*Mdot + (Ne_tmp-Ne_old)*C.mp
    Pn_tmp = Pn_tmp + dt*Pdot

        
#----------------------------------------------------------------------------------------------------------

    if loop_count%1e4 == 0:
        print("---------------------------------")
        print("n={};\t loop_count={}".format(n, loop_count))
        print("Time={};\t\t\t t_tmp (yr) = {:5g};\t\t;\t\t t_free (yr) = {:5g}".format(datetime.now().strftime("%H:%M:%S"), t_tmp/C.yr, t_free/C.yr))
        print('dt (yr)={:5g};\t\t'.format(dt/C.yr))
        print("Rdot={:5g};\t\t vdot={:5g};\t\t Mdot={:5g};\t\t Pdot={:5g}".format(Rdot,vdot,Mdot,Pdot))


    res = fast_Synchrotron_of_gammae(gamma,ng_tmp,(6.0*EB_tmp/(Rn_tmp**3))**0.5,R=Rn_tmp) 
    fctr_tmp = res[2]  #1.0
    L_tmp = res[3]  #0.0   

    loop_count = loop_count+1
    if t_tmp>=t[n+1]:
        #sharp transition at t_free:
        t[n+1] = t_tmp
        Ne[n+1] = Ne_tmp
        ng[n+1,:] = ng_tmp 
        EB[n+1] = EB_tmp    
#         Rn[n+1] = Rn_tmp   
#         vn[n+1] = vn_tmp   
#         Mn[n+1] = Mn_tmp   
#         Pn[n+1] = Pn_tmp  

        gdot_ad[n+1,:]  = (1.0/3.0)*beta**2*gamma*( 3.0*vn_tmp/Rn_tmp ) #- (Edot_of_t(t_tmp)/(chi*(1.0+sigma)))/Ne_tmp )
        gdot_syn[n+1,:] = fctr_tmp*(C.sigT/(np.pi*C.me*C.c))*beta**2*gamma**2*EB_tmp/Rn_tmp**3
        gdot_br[n+1,:]  = (5.0/6.0)*C.c*C.sigT*(1.0/137.0)*(3.0*Ne_tmp/(4.0*np.pi*Rn_tmp**3))*(gamma**1.2)*2.0 # the factor 2 at the end approximates Z*(Z+1)/A for H (it would be ~0.5 for heavy ions)
        gdot_IC[n+1,:]  = (4*C.sigT/(3*C.me*C.c))*beta**2*gamma**2*(L_tmp/(4*np.pi*C.c*Rn_tmp**2))

        n=n+1

runtime = time.time()-runtime
print('------------------------------')
print('\t runtime = {t:.3e} s'.format(t=runtime))
print('------------------------------')

# recast variables into (possibly) shorter arrays (if loop breaks due to max loop count and n<len(t))
t  = t[:n+1]
Ne = Ne[:n+1]
EB = EB[:n+1]                     
vn = vn[:n+1]                     
Rn = Rn[:n+1]                     
Mn = Mn[:n+1]                     
Pn = Pn[:n+1]                     
ng = ng[:n+1,:]                   
gdot_ad  = gdot_ad[:n+1,:]
gdot_syn = gdot_syn[:n+1,:]
gdot_br  = gdot_br[:n+1,:]
gdot_IC  = gdot_IC[:n+1,:]

#################################################################################################################################

# calculate useful quantities
Bn = (6.0*EB/(Rn**3))**0.5

gamma_cool_syn = np.zeros_like(t)
gamma_cool_ad = np.zeros_like(t)
gamma_cool_br = np.zeros_like(t)
gamma_cool_IC = np.zeros_like(t)
Ng_tot = np.zeros_like(t)
Nginj_tot = np.zeros_like(t)
Ng = np.zeros_like(ng)
for n in range(len(t)):
    gamma_cool_syn[n] = 10**np.interp(0.0, np.log10(gdot_syn[n,:]*(t[n]-t[0])/gamma), np.log10(gamma), right=np.log10(gamma[-1]),left=np.log10(gamma[0]))
    gamma_cool_ad[n] = 10**np.interp(0.0, np.log10(gdot_ad[n,:]*(t[n])/gamma), np.log10(gamma), right=np.log10(gamma[-1]),left=np.log10(gamma[0]))
    gamma_cool_br[n] = 10**np.interp(0.0, np.log10(gdot_br[n,:]*(t[n]-t[0])/gamma), np.log10(gamma), right=np.log10(gamma[-1]),left=np.log10(gamma[0]))
    gamma_cool_IC[n] = 10**np.interp(0.0, np.log10(gdot_IC[n,:]*(t[n]-t[0])/gamma), np.log10(gamma), right=np.log10(gamma[-1]),left=np.log10(gamma[0]))
    Ng_tot[n] = np.trapz( (4.0*np.pi*Rn[n]**3/3.0)*ng[n,:]*gamma, x=np.log(gamma) )
    Ng[n,:] = ng[n,:]*(4*np.pi*Rn[n]**3/3.0)

# calculate RM and DM
RM = np.zeros_like(t)
DM = np.zeros_like(t)
for n in range(len(t)):
    RM[n] = (C.q**3/(2*np.pi*C.me**2*C.c**4))*Bn[n]*Rn[n]*(np.trapz( ng[n,:]*gamma**(-2), x=gamma ))*1e4 # "*1e4" to convert to rad / m^2
    DM[n] = Rn[n]*(np.trapz( ng[n,:]*gamma**(-1), x=gamma ))/C.pc # "/pc" to convert to pc / cm^3

nu = 1e9 * 10**np.linspace(-2,4,100)
Lnu = np.zeros((len(t),len(nu)))

for n in range(len(t)):
    Lnu[n,:] = Synchrotron_of_gammae(gamma,ng[n,:],Bn[n],nu,R=Rn[n])

syn = Synchrotron.Synchrotron()
alphanu = np.zeros_like(Lnu)
jnu = np.zeros_like(Lnu)
Lnu_syn = np.zeros_like(Lnu)
Lnu_syn_thin = np.zeros_like(Lnu)
taunu = np.zeros_like(Lnu)
nu_ssa = np.zeros_like(t)
for n in range(len(t)):
    alphanu[n,:] = syn.alpha_nu(gamma,ng[n,:],Bn[n],nu)
    jnu[n,:] = syn.j_nu(gamma,ng[n,:],Bn[n],nu)

    Lnu_syn[n,:] = (np.pi*(4*np.pi*Rn[n]**2))*(jnu[n,:]/alphanu[n,:])*(1.0-np.exp(-alphanu[n,:]*Rn[n]))        
    Lnu_syn_thin[n,:] = (np.pi*(4*np.pi*Rn[n]**2))*(jnu[n,:]*Rn[n])
    taunu[n,:] = alphanu[n,:]*Rn[n]
    #nu_ssa[n] = 10**np.interp(0, np.log(nu),np.log(taunu[n,:]))
    tmp = nu[taunu[n,:]<1e0]
    if np.size(tmp)>1:
        nu_ssa[n] = tmp[0]
    elif np.size(tmp)==1:
        nu_ssa[n] = tmp
    else:
        nu_ssa[n] = nu[-1]

#################################################################################################################################

#Save data:

data={}
data['Ng'] = Ng
data['gamma'] = gamma
data['gammabeta'] = gamma*beta
data['gammadot_syn'] = gdot_syn
data['gammadot_ad'] = gdot_ad
data['gammadot_br'] = gdot_br
data['gammadot_IC'] = gdot_IC
data['gamma_cool_syn'] = gamma_cool_syn
data['gamma_cool_ad'] = gamma_cool_ad
data['gamma_cool_br'] = gamma_cool_br
data['gamma_cool_IC'] = gamma_cool_IC
data['t'] = t
data['Ne'] = Ne

data['nu'] = nu
data['Lnu'] = Lnu
data['Lnu_syn'] = Lnu_syn
data['Lnu_syn_thin'] = Lnu_syn_thin
data['nu_cool'] = (C.q*Bn/(2*np.pi*C.me*C.c))*gamma_cool_syn**2
data['nu_ssa'] = nu_ssa

data['ng'] = ng
data['EB'] = EB
data['Rn'] = Rn
data['Rsh'] = Rsh
data['vn'] = vn
data['Mn'] = Mn
data['Msh'] = Msh
data['t_free'] = t_free
data['t_free_index'] = t_free_index
data['t_active'] = t_active
data['t_active_index'] = t_active_index

data['Bn'] = Bn
data['RM'] = RM
data['DM'] = DM
data['Mn'] = Mn
data['tage'] = []

data['params'] = {}
data['params']['alpha'] = alpha
data['params']['t0'] = t0
data['params']['E_tot'] = E_tot
data['params']['sigma'] = sigma
data['params']['chi'] = chi
data['params']['vej'] = v_w
# data['params']['Mej'] = Mej

pickle.dump(data, open('../models/mdotw5e3_vw1e9_vj0p5c_sigma1_eta1_n10_free_ssimilar_tactive.pkl','wb'), protocol=2)