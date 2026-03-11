**Subject:** Firewall add-on — rule for TCP 8443 not taking effect

---

Hi,

I purchased the firewall add-on and set up an inbound rule so my remote server can reach this one on port 8443, but connections still time out. I'd like to confirm the rule is active and whether anything else could be blocking the traffic.

**Setup:**

- **Firewall group:** TAK-TEST7 (Inbound)
- **Rule:** IPv4, Custom TCP, Port 8443, Source IP 199.241.139.5 (also tried "All"), Target: Accept
- **Linked server:** ssdnodes-66871ef1e08d7 (public IP 63.250.55.132)
- I have clicked **Apply Rules** after creating the rule and linking the group.

**What I'm seeing:**

- From my other server (199.241.139.5), `nc -zv 63.250.55.132 8443` times out.
- On 63.250.55.132 I ran `tcpdump -i any -n port 8443` while running that `nc` from 199.241.139.5. No packets from 199.241.139.5 appear, so the traffic does not seem to reach the VM.
- On 63.250.55.132, UFW allows 8443 and the service is listening; local connections to 8443 work.

So it looks like the traffic is being dropped before it reaches the VM, and I'm not sure if the firewall rule is actually applied at the hypervisor/network layer or if something else is filtering port 8443.

**Can you please:**

1. Confirm that the TAK-TEST7 inbound rule (TCP 8443, Accept) is active for ssdnodes-66871ef1e08d7 (63.250.55.132), and
2. Check whether anything else in your network could be filtering inbound TCP 8443 to this server?

I can provide screenshots of the firewall group, rule, and linked server if that would help.

Thanks,
Andreas
